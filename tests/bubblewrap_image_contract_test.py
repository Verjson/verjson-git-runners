#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "scripts" / "bubblewrap-image-contract.py"
SPEC = importlib.util.spec_from_file_location("bubblewrap_image_contract", CONTRACT_PATH)
assert SPEC is not None and SPEC.loader is not None
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)
FINAL_CONTRACT = 'RUN ["/usr/local/bin/bubblewrap-image-contract"]'
FINAL_CONTRACT_ARGUMENTS = '["/usr/local/bin/bubblewrap-image-contract"]'
ENSURE_COPY_ARGUMENTS = '--chmod=0555 scripts/ensure-bubblewrap.sh /usr/local/bin/ensure-bubblewrap'
ENSURE_RUN_ARGUMENTS = '["/usr/local/bin/ensure-bubblewrap"]'
HELPER_COPY_ARGUMENTS = '--chmod=0555 scripts/bubblewrap-image-contract.py /usr/local/bin/bubblewrap-image-contract'
PROVENANCE_COPY_ARGUMENTS = '--chmod=0444 images/bubblewrap-provenance.json /etc/verjson-bubblewrap-provenance.json'
PACKAGE_ARCHIVE_PATH = '/etc/verjson-bubblewrap.deb'
ROOT_USER_ARGUMENTS = "root"
BUBBLEWRAP_PACKAGE_VERSION = "0.11.1-1ubuntu0.1"
SHIPPED_BUBBLEWRAP_CHECKSUMS = {
    "amd64": {
        "package_sha256": "b353088d1003adb3f760deeccfb84c47928a36c8dc102bf680efc94eb19f4408",
        "binary_sha256": "0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0",
    },
    "arm64": {
        "package_sha256": "7798d8926cf4c51cfc56187703499d75f7ab66d199a700d1093b45916d7120c0",
        "binary_sha256": "29cb90e51494b3765b7b36587b0635863898d1e85025e082674121bcdf34a08b",
    },
}
HEREDOC = re.compile(r"<<(-?)(?:'([^']+)'|\"([^\"]+)\"|([A-Za-z0-9_.-]+))")


def dockerfile_instructions(dockerfile: str) -> list[tuple[str, str]]:
    instructions: list[tuple[str, str]] = []
    continuation = ""
    heredocs: list[tuple[str, bool]] = []
    for physical_line in dockerfile.splitlines():
        if heredocs:
            delimiter, strip_tabs = heredocs[0]
            candidate = physical_line.lstrip("\t") if strip_tabs else physical_line
            if candidate == delimiter:
                heredocs.pop(0)
            continue

        stripped = physical_line.strip()
        if not continuation and (not stripped or stripped.startswith("#")):
            continue
        if continuation and stripped.startswith("#"):
            continue

        continued = stripped.endswith("\\")
        fragment = stripped[:-1].rstrip() if continued else stripped
        continuation = f"{continuation} {fragment}".strip()
        if continued:
            continue

        parsed = re.fullmatch(r"([A-Za-z]+)(?:[ \t]+(.*))?", continuation)
        if parsed is None:
            raise AssertionError(f"invalid Dockerfile instruction: {continuation}")
        instruction, arguments = parsed.groups()
        arguments = (arguments or "").strip()
        instructions.append((instruction.upper(), arguments))
        for match in HEREDOC.finditer(arguments):
            delimiter = next(group for group in match.groups()[1:] if group is not None)
            heredocs.append((delimiter, match.group(1) == "-"))
        continuation = ""

    if continuation:
        raise AssertionError("unterminated Dockerfile continuation")
    if heredocs:
        raise AssertionError("unterminated Dockerfile heredoc")
    return instructions


def assert_final_contract(
    test: unittest.TestCase,
    dockerfile: str,
    allowed_after: tuple[tuple[str, str], ...] = (),
) -> None:
    contract_seen = False
    post_contract: list[tuple[str, str]] = []
    for instruction, arguments in dockerfile_instructions(dockerfile):
        is_contract = instruction == "RUN" and arguments == FINAL_CONTRACT_ARGUMENTS
        if is_contract:
            test.assertFalse(contract_seen, "duplicate final Bubblewrap contract")
            contract_seen = True
            continue
        if contract_seen:
            post_contract.append((instruction, arguments))
    test.assertTrue(contract_seen, "final Bubblewrap contract is missing")
    test.assertEqual(tuple(post_contract), allowed_after)


def assert_helper_is_final_mutation(
    test: unittest.TestCase, instructions: list[tuple[str, str]]
) -> None:
    provenance_indexes = [
        index
        for index, (instruction, arguments) in enumerate(instructions)
        if instruction == "COPY" and arguments == PROVENANCE_COPY_ARGUMENTS
    ]
    test.assertEqual(
        len(provenance_indexes),
        1,
        "Bubblewrap package provenance must be copied exactly once",
    )
    helper_indexes = [
        index
        for index, (instruction, arguments) in enumerate(instructions)
        if instruction == "COPY" and arguments == HELPER_COPY_ARGUMENTS
    ]
    test.assertEqual(
        len(helper_indexes),
        1,
        "Bubblewrap contract helper must be copied exactly once",
    )
    helper_index = helper_indexes[0]
    provenance_index = provenance_indexes[0]
    test.assertLess(provenance_index, helper_index)
    test.assertEqual(
        instructions[provenance_index + 1],
        ("COPY", HELPER_COPY_ARGUMENTS),
        "immutable Bubblewrap provenance must immediately precede the trusted helper",
    )
    later_mutations = [
        (instruction, arguments)
        for instruction, arguments in instructions[helper_index + 1 :]
        if instruction == "COPY"
        or (instruction == "RUN" and arguments != FINAL_CONTRACT_ARGUMENTS)
    ]
    test.assertEqual(
        later_mutations,
        [],
        "no mutating COPY/RUN may follow the trusted Bubblewrap contract helper",
    )


class BubblewrapBehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bin = self.root / "usr" / "bin"
        self.bin.mkdir(parents=True)
        self.root.chmod(0o755)
        (self.root / "usr").chmod(0o755)
        self.bin.chmod(0o755)
        self.owner = os.getuid()
        self.architecture = CONTRACT._host_architecture()
        self.write_bwrap("0.9.0")
        self.write_package_metadata()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_bwrap(self, version: str, path: Path | None = None) -> Path:
        target = path or self.bin / "bwrap"
        target.write_text(f"#!/bin/sh\nprintf 'bubblewrap {version}\\n'\n", encoding="utf-8")
        target.chmod(0o755)
        return target

    def write_package_metadata(self) -> None:
        package_root = self.root / "var" / "lib" / "dpkg"
        info = package_root / "info"
        info.mkdir(parents=True)
        (package_root / "status").write_text(
            "Package: bubblewrap\n"
            "Status: install ok installed\n"
            "Architecture: amd64\n"
            f"Version: {CONTRACT.BUBBLEWRAP_PACKAGE_VERSION}\n"
            "Maintainer: Bubblewrap Test <test@example.invalid>\n"
            "Description: test Bubblewrap package\n\n",
            encoding="utf-8",
        )
        (info / "bubblewrap.list").write_text(
            "/usr/bin/bwrap\n",
            encoding="utf-8",
        )
        self.refresh_package_hash()
        archive = self.root / "etc" / "verjson-bubblewrap.deb"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(b"bubblewrap package archive")
        archive.chmod(0o444)

        self.write_provenance()

    def write_provenance(
        self,
        *,
        package: str = CONTRACT.BUBBLEWRAP_PACKAGE,
        version: str = CONTRACT.BUBBLEWRAP_PACKAGE_VERSION,
        binary_path: str = "/usr/bin/bwrap",
        architecture: str | None = None,
        binary_sha256: str | None = None,
        mode: str = "0755",
        owner: str = "root:root",
    ) -> None:
        etc = self.root / "etc"
        etc.mkdir(parents=True, exist_ok=True)
        etc.chmod(0o755)
        provenance = {
            "package": package,
            "version": version,
            "binary_path": binary_path,
            "architectures": {
                architecture or self.architecture: {
                    "package_sha256": hashlib.sha256(
                        (self.root / "etc" / "verjson-bubblewrap.deb").read_bytes()
                    ).hexdigest(),
                    "binary_sha256": binary_sha256
                    or hashlib.sha256((self.bin / "bwrap").read_bytes()).hexdigest(),
                    "mode": mode,
                    "owner": owner,
                }
            },
        }
        path = etc / CONTRACT.BUBBLEWRAP_PROVENANCE_NAME
        if path.exists():
            path.chmod(0o644)
        path.write_text(json.dumps(provenance) + "\n", encoding="utf-8")
        path.chmod(0o444)

    def refresh_package_hash(self) -> None:
        digest = hashlib.md5((self.bin / "bwrap").read_bytes()).hexdigest()
        (
            self.root / "var" / "lib" / "dpkg" / "info" / "bubblewrap.md5sums"
        ).write_text(
            f"{digest}  usr/bin/bwrap\n",
            encoding="utf-8",
        )

    def verify(self, **kwargs: object) -> None:
        CONTRACT.verify_bubblewrap(self.root, owner=self.owner, **kwargs)

    def test_accepts_exact_minimum_version(self) -> None:
        self.verify()

    def test_rejects_missing_binary(self) -> None:
        (self.bin / "bwrap").unlink()
        with self.assertRaises(CONTRACT.ContractError):
            self.verify()

    def test_rejects_symlinked_binary(self) -> None:
        (self.bin / "bwrap").unlink()
        target = self.write_bwrap("0.9.0", self.bin / "replacement")
        (self.bin / "bwrap").symlink_to(target.name)
        with self.assertRaises(CONTRACT.ContractError):
            self.verify()

    def test_rejects_group_writable_binary(self) -> None:
        (self.bin / "bwrap").chmod(0o775)
        with self.assertRaises(CONTRACT.ContractError):
            self.verify()

    def test_rejects_special_mode_bits(self) -> None:
        for special_mode in (0o4755, 0o2755, 0o1755):
            with self.subTest(mode=oct(special_mode)):
                (self.bin / "bwrap").chmod(special_mode)
                with self.assertRaisesRegex(
                    CONTRACT.ContractError, "special mode bits"
                ):
                    self.verify()
                (self.bin / "bwrap").chmod(0o755)

    def test_rejects_root_owned_version_spoof_with_package_hash_mismatch(self) -> None:
        self.write_bwrap("99.0.0")
        with self.assertRaisesRegex(
            CONTRACT.ContractError, "failed the Bubblewrap package checksum"
        ):
            self.verify()

    def test_rejects_immutable_provenance_with_wrong_binary_path(self) -> None:
        self.write_provenance(binary_path="/usr/bin/other")
        with self.assertRaisesRegex(
            CONTRACT.ContractError, "exact Bubblewrap package"
        ):
            self.verify()

    def test_rejects_replacement_with_rewritten_mutable_package_metadata(self) -> None:
        replacement = self.write_bwrap("99.0.0", self.bin / "replacement")
        replacement.replace(self.bin / "bwrap")
        package_root = self.root / "var" / "lib" / "dpkg"
        (package_root / "status").write_text(
            "Package: bubblewrap\n"
            "Status: install ok installed\n"
            "Architecture: amd64\n"
            f"Version: {CONTRACT.BUBBLEWRAP_PACKAGE_VERSION}\n\n",
            encoding="utf-8",
        )
        (package_root / "info" / "bubblewrap.list").write_text(
            "/usr/bin/bwrap\n",
            encoding="utf-8",
        )
        (package_root / "info" / "bubblewrap.md5sums").write_text(
            f"{hashlib.md5((self.bin / 'bwrap').read_bytes()).hexdigest()}  usr/bin/bwrap\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractError, r"package checksum \(immutable provenance\)"
        ):
            self.verify()

    def test_rejects_wrong_owner(self) -> None:
        with self.assertRaises(CONTRACT.ContractError):
            CONTRACT.verify_bubblewrap(self.root, owner=self.owner + 1)

    def test_root_owner_requirement_is_fail_closed(self) -> None:
        with self.assertRaises(CONTRACT.ContractError):
            CONTRACT.verify_bubblewrap(self.root, owner=0)

    def test_accepts_root_owned_image_when_available(self) -> None:
        if os.geteuid() != 0:
            self.skipTest("root ownership cannot be constructed by an unprivileged test")
        for path in (
            self.root,
            self.root / "usr",
            self.root / "usr" / "bin",
            self.root / "etc",
        ):
            os.chown(path, 0, 0)
        self.owner = 0
        self.write_provenance(owner="root:root")
        self.verify(owner=0)

    def test_rejects_rewritten_package_archive(self) -> None:
        archive = self.root / "etc" / "verjson-bubblewrap.deb"
        archive.chmod(0o644)
        archive.write_bytes(b"replacement package")
        archive.chmod(0o444)
        with self.assertRaisesRegex(CONTRACT.ContractError, "package archive failed"):
            self.verify()

    def test_rejects_package_archive_replaced_during_verification(self) -> None:
        archive = self.root / "etc" / "verjson-bubblewrap.deb"
        replacement = self.root / "etc" / "replacement.deb"
        replacement.write_bytes(b"replacement package")
        replacement.chmod(0o444)

        def replace() -> None:
            replacement.replace(archive)

        with self.assertRaisesRegex(CONTRACT.ContractError, "changed during verification"):
            self.verify(before_execute=replace)

    def test_rejects_fifo_protected_files_without_blocking(self) -> None:
        protected_paths = (
            self.bin / "bwrap",
            self.root / "etc" / CONTRACT.BUBBLEWRAP_PROVENANCE_NAME,
            self.root / "etc" / "verjson-bubblewrap.deb",
        )
        for path in protected_paths:
            with self.subTest(path=path.name):
                path.unlink()
                os.mkfifo(path, 0o444)
                try:
                    with self.assertRaises(CONTRACT.ContractError):
                        self.verify()
                finally:
                    path.unlink()
                    if path.name == "bwrap":
                        self.write_bwrap("0.9.0")
                    elif path.name == CONTRACT.BUBBLEWRAP_PROVENANCE_NAME:
                        self.write_provenance()
                    else:
                        path.write_bytes(b"package archive")
                        path.chmod(0o444)
                        self.write_provenance()

    def test_rejects_writable_package_archive(self) -> None:
        archive = self.root / "etc" / "verjson-bubblewrap.deb"
        archive.chmod(0o644)
        with self.assertRaisesRegex(CONTRACT.ContractError, "package archive is not immutable"):
            self.verify()

    def test_rejects_untrusted_ancestry(self) -> None:
        (self.root / "usr").chmod(0o775)
        with self.assertRaises(CONTRACT.ContractError):
            self.verify()

    def test_rejects_symlinked_ancestry(self) -> None:
        (self.root / "usr").rename(self.root / "real-usr")
        (self.root / "usr").symlink_to("real-usr", target_is_directory=True)
        with self.assertRaises(CONTRACT.ContractError):
            self.verify()

    def test_rejects_version_below_floor(self) -> None:
        self.write_bwrap("0.8.0")
        self.refresh_package_hash()
        self.write_provenance()
        with self.assertRaisesRegex(CONTRACT.ContractError, "older than 0.9.0"):
            self.verify()

    def test_rejects_path_replacement_during_descriptor_bound_execution(self) -> None:
        replacement = self.write_bwrap("99.0.0", self.bin / "replacement")

        def replace() -> None:
            replacement.replace(self.bin / "bwrap")

        with self.assertRaisesRegex(CONTRACT.ContractError, "changed during verification"):
            self.verify(before_execute=replace)

    def test_rejects_ancestry_replacement_during_descriptor_bound_execution(self) -> None:
        def replace() -> None:
            provenance = (
                self.root
                / "etc"
                / CONTRACT.BUBBLEWRAP_PROVENANCE_NAME
            ).read_bytes()
            (self.root / "usr").rename(self.root / "original-usr")
            replacement_usr_bin = self.root / "usr" / "bin"
            replacement_usr_bin.mkdir(parents=True)
            self.root.chmod(0o755)
            (self.root / "usr").chmod(0o755)
            replacement_usr_bin.chmod(0o755)
            provenance_path = self.root / "etc" / CONTRACT.BUBBLEWRAP_PROVENANCE_NAME
            provenance_path.chmod(0o644)
            provenance_path.write_bytes(provenance)
            provenance_path.chmod(0o444)
            self.write_bwrap("99.0.0", replacement_usr_bin / "bwrap")

        with self.assertRaisesRegex(CONTRACT.ContractError, "changed during verification"):
            self.verify(before_execute=replace)


class PublishedImageContractTest(unittest.TestCase):
    def test_bubblewrap_install_is_exactly_version_pinned(self) -> None:
        base = (ROOT / "images/base.Dockerfile").read_text(encoding="utf-8")
        bootstrap = (ROOT / "scripts/ensure-bubblewrap.sh").read_text(encoding="utf-8")
        provenance = json.loads(
            (ROOT / "images/bubblewrap-provenance.json").read_text(encoding="utf-8")
        )
        self.assertIn(
            f"ARG BUBBLEWRAP_VERSION={BUBBLEWRAP_PACKAGE_VERSION}",
            base,
        )
        self.assertIn(f"bubblewrap=${{BUBBLEWRAP_VERSION}}", base)
        self.assertIn(
            f'BUBBLEWRAP_VERSION="${{BUBBLEWRAP_VERSION:-{BUBBLEWRAP_PACKAGE_VERSION}}}"',
            bootstrap,
        )
        self.assertIn('apt-get download "bubblewrap=${BUBBLEWRAP_VERSION}"', base)
        self.assertIn(
            'install -m 0444 "${package_archive}" /etc/verjson-bubblewrap.deb',
            base,
        )
        self.assertEqual(
            CONTRACT_PATH.read_text(encoding="utf-8").splitlines()[0],
            "#!/usr/bin/python3",
        )
        self.assertIn('"bubblewrap=${BUBBLEWRAP_VERSION}"', bootstrap)
        self.assertIn('apt-get download "bubblewrap=${BUBBLEWRAP_VERSION}"', bootstrap)
        self.assertIn('/etc/verjson-bubblewrap.deb', bootstrap)
        self.assertEqual(provenance["package"], "bubblewrap")
        self.assertEqual(provenance["version"], BUBBLEWRAP_PACKAGE_VERSION)
        self.assertEqual(provenance["binary_path"], "/usr/bin/bwrap")
        self.assertEqual(set(provenance["architectures"]), {"amd64", "arm64"})

    def test_shipped_provenance_checksums_are_pinned(self) -> None:
        provenance = json.loads(
            (ROOT / "images/bubblewrap-provenance.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {
                architecture: {
                    key: provenance["architectures"][architecture][key]
                    for key in ("package_sha256", "binary_sha256")
                }
                for architecture in SHIPPED_BUBBLEWRAP_CHECKSUMS
            },
            SHIPPED_BUBBLEWRAP_CHECKSUMS,
        )

    def test_every_published_variant_and_architecture_runs_final_contract(self) -> None:
        config = json.loads((ROOT / "container-candidate.json").read_text(encoding="utf-8"))
        images = config["images"]
        self.assertEqual(
            {image["variant"] for image in images},
            {"base", "rust", "node", "python", "go", "pwsh"},
        )
        expected_platforms = {("linux", "amd64"), ("linux", "arm64")}
        for image in images:
            with self.subTest(variant=image["variant"]):
                self.assertEqual(
                    {(platform["os"], platform["architecture"]) for platform in image["platforms"]},
                    expected_platforms,
                )
                dockerfile = (ROOT / image["file"]).read_text(encoding="utf-8")
                instructions = dockerfile_instructions(dockerfile)
                ensure_indexes = [
                    index
                    for index, (instruction, arguments) in enumerate(instructions)
                    if instruction == "COPY" and arguments == ENSURE_COPY_ARGUMENTS
                ]
                helper_indexes = [
                    index
                    for index, (instruction, arguments) in enumerate(instructions)
                    if instruction == "COPY" and arguments == HELPER_COPY_ARGUMENTS
                ]
                provenance_indexes = [
                    index
                    for index, (instruction, arguments) in enumerate(instructions)
                    if instruction == "COPY" and arguments == PROVENANCE_COPY_ARGUMENTS
                ]
                contract_indexes = [
                    index
                    for index, (instruction, arguments) in enumerate(instructions)
                    if instruction == "RUN" and arguments == FINAL_CONTRACT_ARGUMENTS
                ]
                self.assertEqual(
                    len(helper_indexes),
                    1,
                    "Bubblewrap contract helper must be copied exactly once",
                )
                self.assertEqual(len(provenance_indexes), 1)
                self.assertEqual(len(contract_indexes), 1)
                if image["variant"] == "base":
                    self.assertEqual(ensure_indexes, [])
                else:
                    self.assertEqual(
                        len(ensure_indexes),
                        1,
                        "standalone variants must bootstrap Bubblewrap exactly once",
                    )
                    ensure_run_indexes = [
                        index
                        for index, (instruction, arguments) in enumerate(instructions)
                        if instruction == "RUN" and arguments == ENSURE_RUN_ARGUMENTS
                    ]
                    self.assertEqual(len(ensure_run_indexes), 1)
                    self.assertLess(ensure_indexes[0], contract_indexes[0])
                    self.assertLess(ensure_run_indexes[0], contract_indexes[0])
                    root_user_indexes = [
                        index
                        for index, (instruction, arguments) in enumerate(instructions)
                        if instruction == "USER" and arguments == ROOT_USER_ARGUMENTS
                    ]
                    self.assertTrue(
                        any(index < ensure_run_indexes[0] for index in root_user_indexes),
                        "standalone bootstrap must run as root",
                    )
                self.assertLess(helper_indexes[0], contract_indexes[0])
                assert_helper_is_final_mutation(self, instructions)
                self.assertEqual(
                    instructions[helper_indexes[0] + 1],
                    ("USER", "runner"),
                    "trusted Bubblewrap contract helper must precede the final runner user",
                )
                self.assertEqual(
                    instructions[helper_indexes[0] + 2],
                    ("RUN", FINAL_CONTRACT_ARGUMENTS),
                    "final Bubblewrap contract must immediately follow the runner user",
                )
                allowed_after = (
                    (("ENTRYPOINT", '["/entrypoint.sh"]'),)
                    if image["variant"] == "base"
                    else ()
                )
                assert_final_contract(self, dockerfile, allowed_after)

    def test_removing_final_contract_fails(self) -> None:
        with self.assertRaises(AssertionError):
            assert_final_contract(self, "FROM base\nUSER runner\n")

    def test_replacing_bwrap_after_final_contract_fails(self) -> None:
        mutated = (
            "FROM base\n"
            f"{FINAL_CONTRACT}\n"
            "COPY replacement /usr/bin/bwrap\n"
        )
        with self.assertRaises(AssertionError):
            assert_final_contract(self, mutated)

    def test_copy_after_helper_fails(self) -> None:
        mutated = (
            "FROM base\n"
            f"COPY {HELPER_COPY_ARGUMENTS.split(' ', 1)[1]}\n"
            "COPY replacement /usr/bin/bwrap\n"
            f"{FINAL_CONTRACT}\n"
        )
        with self.assertRaises(AssertionError):
            assert_helper_is_final_mutation(self, dockerfile_instructions(mutated))

    def test_run_after_helper_fails(self) -> None:
        mutated = (
            "FROM base\n"
            f"COPY {HELPER_COPY_ARGUMENTS.split(' ', 1)[1]}\n"
            "RUN touch /usr/bin/bwrap\n"
            f"{FINAL_CONTRACT}\n"
        )
        with self.assertRaises(AssertionError):
            assert_helper_is_final_mutation(self, dockerfile_instructions(mutated))

    def test_later_from_scratch_fails(self) -> None:
        mutated = f"FROM base\n{FINAL_CONTRACT}\nFROM scratch\n"
        with self.assertRaises(AssertionError):
            assert_final_contract(self, mutated)

    def test_lowercase_mutation_after_final_contract_fails(self) -> None:
        mutated = f"FROM base\n{FINAL_CONTRACT}\nrun touch /usr/bin/bwrap\n"
        with self.assertRaises(AssertionError):
            assert_final_contract(self, mutated)

    def test_leading_whitespace_mutation_after_final_contract_fails(self) -> None:
        mutated = f"FROM base\n{FINAL_CONTRACT}\n  COPY replacement /usr/bin/bwrap\n"
        with self.assertRaises(AssertionError):
            assert_final_contract(self, mutated)

    def test_continued_contract_with_extra_command_fails(self) -> None:
        mutated = (
            "FROM base\n"
            f"{FINAL_CONTRACT} \\\n"
            "  && touch /usr/bin/bwrap\n"
        )
        with self.assertRaises(AssertionError):
            assert_final_contract(self, mutated)

    def test_comment_inside_mutating_continuation_does_not_hide_it(self) -> None:
        mutated = (
            "FROM base\n"
            f"{FINAL_CONTRACT} \\\n"
            "  # ignored continuation comment\n"
            "  && touch /usr/bin/bwrap\n"
        )
        with self.assertRaises(AssertionError):
            assert_final_contract(self, mutated)

    def test_comments_and_entrypoint_after_final_contract_are_accepted(self) -> None:
        dockerfile = (
            "FROM base\n"
            f"  {FINAL_CONTRACT}\n"
            "  # a comment is not an instruction\n"
            "entrypoint [\"/entrypoint.sh\"]\n"
        )
        assert_final_contract(
            self, dockerfile, (("ENTRYPOINT", '["/entrypoint.sh"]'),)
        )

    def test_hostile_entrypoint_after_final_contract_fails(self) -> None:
        mutated = (
            "FROM base\n"
            f"{FINAL_CONTRACT}\n"
            "ENTRYPOINT [\"/bin/true\"]\n"
        )
        with self.assertRaises(AssertionError):
            assert_final_contract(
                self, mutated, (("ENTRYPOINT", '["/entrypoint.sh"]'),)
            )

    def test_shell_form_contract_under_hostile_shell_fails(self) -> None:
        mutated = (
            "FROM base\n"
            "SHELL [\"/bin/true\"]\n"
            "RUN /usr/local/bin/bubblewrap-image-contract\n"
        )
        with self.assertRaises(AssertionError):
            assert_final_contract(self, mutated)

    def test_false_contract_inside_run_heredoc_fails(self) -> None:
        mutated = (
            "FROM base\n"
            "RUN <<'SCRIPT'\n"
            f"{FINAL_CONTRACT}\n"
            "SCRIPT\n"
        )
        with self.assertRaises(AssertionError):
            assert_final_contract(self, mutated)


if __name__ == "__main__":
    unittest.main()
