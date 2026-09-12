#!/usr/bin/python3
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tarfile
from collections.abc import Callable
from pathlib import Path

MINIMUM_VERSION = (0, 9, 0)
BUBBLEWRAP_PACKAGE = "bubblewrap"
BUBBLEWRAP_PACKAGE_VERSION = "0.11.1-1ubuntu0.1"
BUBBLEWRAP_PROVENANCE_PATH = "/etc/verjson-bubblewrap-provenance.json"
BUBBLEWRAP_PROVENANCE_NAME = Path(BUBBLEWRAP_PROVENANCE_PATH).name
BUBBLEWRAP_PACKAGE_ARCHIVE_NAME = "verjson-bubblewrap.deb"
BUBBLEWRAP_PACKAGE_ANCHOR_PATH = "/etc/verjson-bubblewrap-apt-sha256.json"
BUBBLEWRAP_PACKAGE_ANCHOR_NAME = Path(BUBBLEWRAP_PACKAGE_ANCHOR_PATH).name


class ContractError(RuntimeError):
    pass


def _trusted_directory(parent_fd: int, name: str, display: str, owner: int) -> int:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise ContractError(f"{display} is not a trusted directory") from error

    metadata = os.fstat(descriptor)
    if metadata.st_uid != owner or metadata.st_gid != owner:
        os.close(descriptor)
        raise ContractError(f"{display} must be owned by root:root")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        os.close(descriptor)
        raise ContractError(f"{display} must not be group- or world-writable")
    return descriptor


def _open_bubblewrap(bin_fd: int, owner: int) -> tuple[int, os.stat_result]:
    try:
        descriptor = os.open(
            "bwrap",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=bin_fd,
        )
    except OSError as error:
        raise ContractError("/usr/bin/bwrap is not an exact regular file") from error

    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise ContractError("/usr/bin/bwrap is not an exact regular file")
    if metadata.st_uid != owner or metadata.st_gid != owner:
        os.close(descriptor)
        raise ContractError("/usr/bin/bwrap must be owned by root:root")
    mode = stat.S_IMODE(metadata.st_mode)
    if mode & (0o022 | stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
        os.close(descriptor)
        raise ContractError("/usr/bin/bwrap must not be writable or have special mode bits")
    if not mode & 0o111:
        os.close(descriptor)
        raise ContractError("/usr/bin/bwrap must be executable")
    return descriptor, metadata


def _host_architecture() -> str:
    architecture = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(os.uname().machine)
    if architecture is None:
        raise ContractError("Bubblewrap package provenance has an unsupported architecture")
    return architecture


def _read_provenance(provenance_fd: int, metadata: os.stat_result) -> dict[str, object]:
    if metadata.st_size > 64 * 1024:
        raise ContractError("Bubblewrap package provenance is too large")
    try:
        contents = os.pread(provenance_fd, metadata.st_size, 0)
    except OSError as error:
        raise ContractError("Bubblewrap package provenance is unreadable") from error
    if len(contents) != metadata.st_size:
        raise ContractError("Bubblewrap package provenance is truncated")
    try:
        provenance = json.loads(contents)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("Bubblewrap package provenance is invalid") from error
    if not isinstance(provenance, dict):
        raise ContractError("Bubblewrap package provenance is invalid")
    return provenance


def _hash_fd(descriptor: int, display: str) -> str:
    digest = hashlib.sha256()
    offset = 0
    try:
        while chunk := os.pread(descriptor, 1024 * 1024, offset):
            digest.update(chunk)
            offset += len(chunk)
    except OSError as error:
        raise ContractError(f"{display} could not be hashed") from error
    return digest.hexdigest()


def _open_package_archive(etc_fd: int, owner: int) -> tuple[int, os.stat_result]:
    try:
        descriptor = os.open(
            BUBBLEWRAP_PACKAGE_ARCHIVE_NAME,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=etc_fd,
        )
    except OSError as error:
        raise ContractError("Bubblewrap package archive is missing") from error
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != owner
        or metadata.st_gid != owner
        or stat.S_IMODE(metadata.st_mode) != 0o444
    ):
        os.close(descriptor)
        raise ContractError("Bubblewrap package archive is not immutable")
    return descriptor, metadata


def _package_binary_hash(package_archive_fd: int) -> str:
    try:
        package = subprocess.run(
            ["dpkg-deb", "--fsys-tarfile", f"/proc/self/fd/{package_archive_fd}"],
            check=True,
            capture_output=True,
            pass_fds=(package_archive_fd,),
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ContractError("Bubblewrap package archive is not a readable Debian package") from error

    try:
        with tarfile.open(fileobj=io.BytesIO(package.stdout), mode="r:") as filesystem:
            binary = next(
                (
                    member
                    for member in filesystem.getmembers()
                    if member.name.lstrip("./") == "usr/bin/bwrap"
                ),
                None,
            )
            if binary is None or not binary.isfile():
                raise ContractError("Bubblewrap package archive has no regular usr/bin/bwrap")
            stream = filesystem.extractfile(binary)
            if stream is None:
                raise ContractError("Bubblewrap package archive binary is unreadable")
            digest = hashlib.sha256()
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
            return digest.hexdigest()
    except (OSError, tarfile.TarError) as error:
        raise ContractError("Bubblewrap package archive filesystem is unreadable") from error


def _read_package_anchor(anchor_fd: int, metadata: os.stat_result, architecture: str) -> str:
    if metadata.st_size > 16 * 1024:
        raise ContractError("Bubblewrap package checksum anchor is too large")
    try:
        contents = os.pread(anchor_fd, metadata.st_size, 0)
        anchor = json.loads(contents)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("Bubblewrap package checksum anchor is invalid") from error
    if not isinstance(anchor, dict) or set(anchor) != {"package", "version", "architecture", "sha256"}:
        raise ContractError("Bubblewrap package checksum anchor is invalid")
    checksum = anchor["sha256"]
    if (
        anchor["package"] != BUBBLEWRAP_PACKAGE
        or anchor["version"] != BUBBLEWRAP_PACKAGE_VERSION
        or anchor["architecture"] != architecture
        or not isinstance(checksum, str)
        or not re.fullmatch(r"[0-9a-f]{64}", checksum)
    ):
        raise ContractError("Bubblewrap package checksum anchor is invalid")
    return checksum


def _open_package_anchor(etc_fd: int, owner: int) -> tuple[int, os.stat_result]:
    try:
        descriptor = os.open(
            BUBBLEWRAP_PACKAGE_ANCHOR_NAME,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=etc_fd,
        )
    except OSError as error:
        raise ContractError("Bubblewrap package checksum anchor is unavailable") from error
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != owner
        or metadata.st_gid != owner
        or stat.S_IMODE(metadata.st_mode) != 0o444
    ):
        os.close(descriptor)
        raise ContractError("Bubblewrap package checksum anchor is not immutable")
    return descriptor, metadata


def _verify_bubblewrap_package(
    provenance_fd: int,
    provenance_metadata: os.stat_result,
    anchor_fd: int,
    anchor_metadata: os.stat_result,
    package_archive_fd: int,
    bubblewrap_fd: int,
    bubblewrap_metadata: os.stat_result,
) -> None:
    provenance = _read_provenance(provenance_fd, provenance_metadata)
    if set(provenance) != {"package", "version", "binary_path", "architectures"}:
        raise ContractError("Bubblewrap package provenance is invalid")
    if (
        provenance["package"] != BUBBLEWRAP_PACKAGE
        or provenance["version"] != BUBBLEWRAP_PACKAGE_VERSION
        or provenance["binary_path"] != "/usr/bin/bwrap"
        or not isinstance(provenance["architectures"], dict)
    ):
        raise ContractError("/usr/bin/bwrap is not provided by the exact Bubblewrap package")

    architecture = _host_architecture()
    record = provenance["architectures"].get(architecture)
    if not isinstance(record, dict) or set(record) != {"mode", "owner", "package_sha256"}:
        raise ContractError("Bubblewrap package provenance has no exact architecture record")
    mode = record["mode"]
    package_sha256 = record["package_sha256"]
    if (
        record["owner"] != "root:root"
        or not isinstance(mode, str)
        or mode != "0755"
        or not isinstance(package_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", package_sha256)
    ):
        raise ContractError("Bubblewrap package provenance is invalid")

    anchor_sha256 = _read_package_anchor(anchor_fd, anchor_metadata, architecture)
    if anchor_sha256 != package_sha256:
        raise ContractError("Bubblewrap package checksum anchor differs from immutable provenance")
    if _hash_fd(package_archive_fd, "Bubblewrap package archive") != package_sha256:
        raise ContractError("Bubblewrap package archive failed the authenticated APT checksum")
    if _hash_fd(bubblewrap_fd, "/usr/bin/bwrap") != _package_binary_hash(package_archive_fd):
        raise ContractError("/usr/bin/bwrap differs from the authenticated Bubblewrap package")
    if stat.S_IMODE(bubblewrap_metadata.st_mode) != int(mode, 8):
        raise ContractError("/usr/bin/bwrap has an unexpected package mode")


def verify_bubblewrap(
    root: Path = Path("/"),
    *,
    owner: int = 0,
    before_execute: Callable[[], None] | None = None,
) -> None:
    def identity(metadata: os.stat_result) -> tuple[int, ...]:
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_uid,
            metadata.st_gid,
            stat.S_IMODE(metadata.st_mode),
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )

    try:
        root_fd = os.open(
            root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
    except OSError as error:
        raise ContractError("/ is not a trusted directory") from error

    descriptors = [root_fd]
    try:
        root_metadata = os.fstat(root_fd)
        if root_metadata.st_uid != owner or root_metadata.st_gid != owner:
            raise ContractError("/ must be owned by root:root")
        if stat.S_IMODE(root_metadata.st_mode) & 0o022:
            raise ContractError("/ must not be group- or world-writable")

        usr_fd = _trusted_directory(root_fd, "usr", "/usr", owner)
        descriptors.append(usr_fd)
        usr_before = os.fstat(usr_fd)
        etc_fd = _trusted_directory(root_fd, "etc", "/etc", owner)
        descriptors.append(etc_fd)
        etc_before = os.fstat(etc_fd)
        try:
            provenance_fd = os.open(
                BUBBLEWRAP_PROVENANCE_NAME,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                dir_fd=etc_fd,
            )
        except OSError as error:
            raise ContractError("Bubblewrap package provenance is unavailable") from error
        descriptors.append(provenance_fd)
        provenance_before = os.fstat(provenance_fd)
        if (
            not stat.S_ISREG(provenance_before.st_mode)
            or provenance_before.st_uid != owner
            or provenance_before.st_gid != owner
            or stat.S_IMODE(provenance_before.st_mode) != 0o444
        ):
            raise ContractError("Bubblewrap package provenance is not immutable")
        package_archive_fd, package_archive_before = _open_package_archive(etc_fd, owner)
        descriptors.append(package_archive_fd)
        anchor_fd, anchor_before = _open_package_anchor(etc_fd, owner)
        descriptors.append(anchor_fd)
        bin_fd = _trusted_directory(usr_fd, "bin", "/usr/bin", owner)
        descriptors.append(bin_fd)
        bin_before = os.fstat(bin_fd)
        bubblewrap_fd, before = _open_bubblewrap(bin_fd, owner)
        descriptors.append(bubblewrap_fd)

        _verify_bubblewrap_package(
            provenance_fd,
            provenance_before,
            anchor_fd,
            anchor_before,
            package_archive_fd,
            bubblewrap_fd,
            before,
        )

        if before_execute is not None:
            before_execute()

        result = subprocess.run(
            [f"/proc/self/fd/{bubblewrap_fd}", "--version"],
            pass_fds=(bubblewrap_fd,),
            check=False,
            capture_output=True,
            text=True,
            env={"LC_ALL": "C"},
        )
        if result.returncode != 0:
            raise ContractError("/usr/bin/bwrap --version failed")

        match = re.fullmatch(r"bubblewrap ([0-9]+)\.([0-9]+)\.([0-9]+)\n?", result.stdout)
        if match is None:
            raise ContractError("/usr/bin/bwrap emitted an unsupported version string")
        if tuple(map(int, match.groups())) < MINIMUM_VERSION:
            raise ContractError("/usr/bin/bwrap is older than 0.9.0")

        usr_after_fd = _trusted_directory(root_fd, "usr", "/usr", owner)
        descriptors.append(usr_after_fd)
        etc_after_fd = _trusted_directory(root_fd, "etc", "/etc", owner)
        descriptors.append(etc_after_fd)
        try:
            provenance_after_fd = os.open(
                BUBBLEWRAP_PROVENANCE_NAME,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                dir_fd=etc_after_fd,
            )
        except OSError as error:
            raise ContractError("Bubblewrap package provenance is unavailable") from error
        descriptors.append(provenance_after_fd)
        provenance_after = os.fstat(provenance_after_fd)
        anchor_after_fd, anchor_after = _open_package_anchor(etc_after_fd, owner)
        descriptors.append(anchor_after_fd)
        bin_after_fd = _trusted_directory(usr_after_fd, "bin", "/usr/bin", owner)
        descriptors.append(bin_after_fd)
        after_fd, after = _open_bubblewrap(bin_after_fd, owner)
        descriptors.append(after_fd)
        package_archive_after_fd, package_archive_after = _open_package_archive(
            etc_after_fd, owner
        )
        descriptors.append(package_archive_after_fd)
        if (
            identity(before) != identity(after)
            or identity(package_archive_before) != identity(package_archive_after)
            or identity(anchor_before) != identity(anchor_after)
        ):
            raise ContractError("/usr/bin/bwrap changed during verification")
        _verify_bubblewrap_package(
            provenance_after_fd,
            provenance_after,
            anchor_after_fd,
            anchor_after,
            package_archive_after_fd,
            after_fd,
            after,
        )
        if (
            identity(usr_before) != identity(os.fstat(usr_fd))
            or identity(usr_before) != identity(os.fstat(usr_after_fd))
            or identity(etc_before) != identity(os.fstat(etc_fd))
            or identity(etc_before) != identity(os.fstat(etc_after_fd))
            or identity(provenance_before) != identity(os.fstat(provenance_fd))
            or identity(provenance_before) != identity(provenance_after)
            or identity(package_archive_before) != identity(os.fstat(package_archive_fd))
            or identity(package_archive_before) != identity(package_archive_after)
            or identity(anchor_before) != identity(os.fstat(anchor_fd))
            or identity(anchor_before) != identity(anchor_after)
            or identity(bin_before) != identity(os.fstat(bin_fd))
            or identity(bin_before) != identity(os.fstat(bin_after_fd))
            or identity(before) != identity(os.fstat(bubblewrap_fd))
            or identity(before) != identity(after)
        ):
            raise ContractError("/usr/bin/bwrap changed during verification")
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


if __name__ == "__main__":
    try:
        verify_bubblewrap()
    except ContractError as error:
        raise SystemExit(f"bubblewrap image contract: {error}") from None
