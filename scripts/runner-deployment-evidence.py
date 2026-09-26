#!/usr/bin/env python3
"""Evidence adapter for container_deployment_controller.py's collect-evidence step.

Invoked as this repository's reviewed `evidenceCommand` (container-deployment.json),
this process runs in the controller's stripped subprocess sandbox: only PATH, LANG,
LC_ALL, TMPDIR, SSL_CERT_FILE, and SSL_CERT_DIR reach it, so there is no GH_TOKEN,
App JWT, or SSH credential available here. Every GitHub read below is therefore an
unauthenticated call against Verjson/verjson-git-runners' public release assets —
the controller's own privileged host-export transport (container_deployment_transport.py,
running with a minted App JWT) independently re-fetches and cryptographically
verifies the manifest and attestation this adapter proposes before trusting it.

Known limitation: --rollback-receipt is not implemented. Retained deployment
receipts exist only as 90-day GitHub Actions artifacts, and downloading an
artifact's content requires authentication this sandbox does not have (listing
artifacts is unauthenticated-readable for a public repository; downloading one
is not). See Verjson/verjson-git-runners#223.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

MANIFEST_IDENTITY = re.compile(r"sha256:[0-9a-f]{64}")
STABLE_SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
CONFIG_NAME = "container-deployment.json"
RELEASES_SUBDIR = Path("RELEASES") / "containers"
GITHUB_API = "https://api.github.com"
USER_AGENT = "verjson-runner-deployment-evidence"
DEFAULT_ROOT = Path(".")

Opener = Callable[..., Any]


class EvidenceError(Exception):
    """A reviewed, fail-closed evidence-collection failure."""


def git_head_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def git_head_tree(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_NAME
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise EvidenceError(f"{CONFIG_NAME} is not readable") from error
    try:
        config = json.loads(raw)
    except ValueError as error:
        raise EvidenceError(f"{CONFIG_NAME} is not valid JSON") from error
    if not isinstance(config, dict):
        raise EvidenceError(f"{CONFIG_NAME} must be a JSON object")
    return config


def find_local_manifest(root: Path, manifest_identity: str) -> tuple[str, bytes]:
    directory = root / RELEASES_SUBDIR
    if not directory.is_dir():
        raise EvidenceError(f"{RELEASES_SUBDIR} does not exist in this checkout")
    digest = manifest_identity.split(":", 1)[1]
    for path in sorted(directory.glob("*.json")):
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() == digest:
            try:
                manifest = json.loads(raw)
            except ValueError as error:
                raise EvidenceError(f"{path} is not valid JSON") from error
            if not isinstance(manifest, dict):
                raise EvidenceError(f"{path} must be a JSON object")
            version = manifest.get("releaseVersion")
            if not isinstance(version, str) or STABLE_SEMVER.fullmatch(version) is None:
                raise EvidenceError(f"{path} releaseVersion must be stable SemVer")
            return version, raw
    raise EvidenceError(
        f"no locally retained release manifest under {RELEASES_SUBDIR} matches {manifest_identity}"
    )


def _get_json(url: str, opener: Opener) -> Any:
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    try:
        with opener(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        raise EvidenceError(f"{url} returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise EvidenceError(f"{url} was unreachable: {error.reason}") from error
    try:
        return json.loads(payload)
    except ValueError as error:
        raise EvidenceError(f"{url} did not return valid JSON") from error


def fetch_release_asset_id(repository: str, version: str, *, opener: Opener = urllib.request.urlopen) -> tuple[int, int]:
    url = f"{GITHUB_API}/repos/{repository}/releases/tags/v{version}"
    payload = _get_json(url, opener)
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        raise EvidenceError(f"release v{version} has no asset list")
    matches = [
        asset for asset in assets
        if isinstance(asset, dict) and asset.get("name") == "release-manifest.json"
    ]
    if len(matches) != 1:
        raise EvidenceError(
            f"release v{version} does not have exactly one release-manifest.json asset"
        )
    asset_id = matches[0].get("id")
    size = matches[0].get("size")
    if not isinstance(asset_id, int) or isinstance(asset_id, bool) or asset_id < 1:
        raise EvidenceError(f"release v{version} release-manifest.json asset id is invalid")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise EvidenceError(f"release v{version} release-manifest.json asset size is invalid")
    return asset_id, size


def fetch_asset_bytes(repository: str, asset_id: int, *, opener: Opener = urllib.request.urlopen) -> bytes:
    url = f"{GITHUB_API}/repos/{repository}/releases/assets/{asset_id}"
    request = urllib.request.Request(
        url, headers={"Accept": "application/octet-stream", "User-Agent": USER_AGENT},
    )
    try:
        with opener(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise EvidenceError(f"release asset {asset_id} download failed: HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise EvidenceError(f"release asset {asset_id} download failed: {error.reason}") from error


def collect_evidence(
    root: Path,
    manifest_identity: str,
    rollback_receipt: str,
    *,
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    if MANIFEST_IDENTITY.fullmatch(manifest_identity) is None:
        raise EvidenceError("manifest identity must be an immutable sha256 digest reference")
    if rollback_receipt:
        raise EvidenceError(
            "rollback receipt retrieval is not implemented: this sandboxed adapter has no "
            "credentialed path to download a retained deployment-receipts artifact "
            "(GitHub Actions artifact downloads require authentication even for a public "
            "repository); see Verjson/verjson-git-runners#223"
        )
    config = load_config(root)
    expected = config.get("expectedRelease")
    if not isinstance(expected, dict):
        raise EvidenceError(f"{CONFIG_NAME} expectedRelease is missing")
    repository = expected.get("sourceRepository")
    if not isinstance(repository, str) or not repository:
        raise EvidenceError(f"{CONFIG_NAME} expectedRelease.sourceRepository is missing")

    version, local_bytes = find_local_manifest(root, manifest_identity)
    asset_id, size = fetch_release_asset_id(repository, version, opener=opener)
    remote_bytes = fetch_asset_bytes(repository, asset_id, opener=opener)

    if len(remote_bytes) != size:
        raise EvidenceError("release asset size differs from reviewed metadata")
    digest = manifest_identity.split(":", 1)[1]
    if hashlib.sha256(remote_bytes).hexdigest() != digest:
        raise EvidenceError("release asset bytes differ from the requested manifest identity")
    if remote_bytes != local_bytes:
        raise EvidenceError("release asset bytes differ from the locally retained manifest")
    try:
        manifest_text = remote_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise EvidenceError("release asset bytes are not valid UTF-8") from error
    try:
        manifest = json.loads(manifest_text)
    except ValueError as error:
        raise EvidenceError("release asset bytes are not valid JSON") from error

    evidence: dict[str, Any] = {
        "headCommit": git_head_commit(root),
        "headTree": git_head_tree(root),
        # GITHUB_RUN_ATTEMPT is not in this sandbox's environment allowlist and
        # has no other local channel to this process; 1 is correct for every
        # first attempt (the overwhelming common case for a mutating deploy)
        # and the controller fails closed on an actual re-run, rather than
        # silently misreporting one.
        "workflowRunAttempt": 1,
        "manifestIdentity": manifest_identity,
        "manifest": manifest,
        "manifestBytes": manifest_text,
        "releaseAssetId": asset_id,
    }
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-identity", required=True)
    parser.add_argument("--fleet", required=True)
    parser.add_argument("--rollback-receipt", default="")
    args = parser.parse_args(argv)
    try:
        evidence = collect_evidence(
            DEFAULT_ROOT, args.manifest_identity, args.rollback_receipt,
            opener=urllib.request.urlopen,
        )
    except EvidenceError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    json.dump(evidence, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
