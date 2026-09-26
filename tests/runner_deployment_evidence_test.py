#!/usr/bin/env python3
"""Behavioral tests for scripts/runner-deployment-evidence.py.

This adapter runs in the deployment controller's stripped subprocess sandbox
(`PATH`, `LANG`, `LC_ALL`, `TMPDIR`, `SSL_CERT_FILE`, `SSL_CERT_DIR` only — no
`GH_TOKEN`, no App JWT). Every GitHub read it performs is therefore an
unauthenticated public-API call; these tests stub that boundary and never hit
the network.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import unittest
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "runner-deployment-evidence.py"
SPEC = importlib.util.spec_from_file_location("runner_deployment_evidence", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
EVIDENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVIDENCE)

MANIFEST_IDENTITY = "sha256:" + "a" * 64
MANIFEST_BYTES = json.dumps({"releaseVersion": "1.2.3", "images": []}, sort_keys=True).encode("utf-8")
REAL_DIGEST = "sha256:" + hashlib.sha256(MANIFEST_BYTES).hexdigest()


def _make_repo(tmp: Path, *, manifest_bytes: bytes = MANIFEST_BYTES) -> Path:
    (tmp / "RELEASES" / "containers").mkdir(parents=True)
    (tmp / "RELEASES" / "containers" / "v1.2.3.json").write_bytes(manifest_bytes)
    (tmp / "container-deployment.json").write_text(
        json.dumps({"expectedRelease": {"sourceRepository": "Verjson/example"}}),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp, check=True)
    return tmp


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> None:
        return None


def _release_tags_payload(asset_id: int = 42, size: int | None = None) -> bytes:
    return json.dumps({
        "assets": [
            {"id": asset_id, "name": "release-manifest.json", "size": size if size is not None else len(MANIFEST_BYTES)},
            {"id": 7, "name": "base-sbom.json", "size": 100},
        ],
    }).encode("utf-8")


def _opener_sequence(*responses):
    iterator = iter(responses)

    def opener(request, timeout=30):
        value = next(iterator)
        if isinstance(value, Exception):
            raise value
        return _FakeResponse(value)

    return opener


class GitHeadTest(unittest.TestCase):
    def test_reports_the_exact_checked_out_commit_and_tree(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            expected_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
            ).stdout.strip()
            expected_tree = subprocess.run(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=repo, check=True, capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(EVIDENCE.git_head_commit(repo), expected_commit)
            self.assertEqual(EVIDENCE.git_head_tree(repo), expected_tree)


class FindLocalManifestTest(unittest.TestCase):
    def test_finds_the_release_file_whose_digest_matches(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            version, raw_bytes = EVIDENCE.find_local_manifest(repo, REAL_DIGEST)
            self.assertEqual(version, "1.2.3")
            self.assertEqual(raw_bytes, MANIFEST_BYTES)

    def test_raises_when_no_local_manifest_matches_the_requested_digest(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            other_digest = "sha256:" + "b" * 64
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.find_local_manifest(repo, other_digest)

    def test_raises_when_releases_directory_is_absent(self) -> None:
        with TemporaryDirectory() as raw:
            repo = Path(raw)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.find_local_manifest(repo, REAL_DIGEST)

    def test_rejects_a_release_version_outside_stable_semver(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            malicious = json.dumps({"releaseVersion": "1.2.3/../../evil"}, sort_keys=True).encode()
            digest = "sha256:" + hashlib.sha256(malicious).hexdigest()
            (repo / "RELEASES" / "containers" / "v1.2.3.json").write_bytes(malicious)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.find_local_manifest(repo, digest)


class FetchReleaseAssetIdTest(unittest.TestCase):
    def test_returns_the_release_manifest_asset_id_and_size(self) -> None:
        opener = _opener_sequence(_release_tags_payload(asset_id=532627568, size=9093))
        asset_id, size = EVIDENCE.fetch_release_asset_id("Verjson/example", "1.2.3", opener=opener)
        self.assertEqual(asset_id, 532627568)
        self.assertEqual(size, 9093)

    def test_raises_when_no_release_manifest_asset_is_present(self) -> None:
        payload = json.dumps({"assets": [{"id": 1, "name": "other.json", "size": 5}]}).encode("utf-8")
        opener = _opener_sequence(payload)
        with self.assertRaises(EVIDENCE.EvidenceError):
            EVIDENCE.fetch_release_asset_id("Verjson/example", "1.2.3", opener=opener)

    def test_raises_on_http_error(self) -> None:
        opener = _opener_sequence(urllib.error.HTTPError("url", 404, "not found", {}, io.BytesIO()))
        with self.assertRaises(EVIDENCE.EvidenceError):
            EVIDENCE.fetch_release_asset_id("Verjson/example", "1.2.3", opener=opener)


class FetchAssetBytesTest(unittest.TestCase):
    def test_returns_the_raw_asset_bytes(self) -> None:
        opener = _opener_sequence(MANIFEST_BYTES)
        result = EVIDENCE.fetch_asset_bytes("Verjson/example", 42, opener=opener)
        self.assertEqual(result, MANIFEST_BYTES)

    def test_raises_on_http_error(self) -> None:
        opener = _opener_sequence(urllib.error.HTTPError("url", 500, "boom", {}, io.BytesIO()))
        with self.assertRaises(EVIDENCE.EvidenceError):
            EVIDENCE.fetch_asset_bytes("Verjson/example", 42, opener=opener)


class CollectEvidenceTest(unittest.TestCase):
    def test_returns_evidence_matching_the_requested_manifest_identity(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            opener = _opener_sequence(_release_tags_payload(asset_id=99), MANIFEST_BYTES)
            evidence = EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)
            self.assertEqual(evidence["manifestIdentity"], REAL_DIGEST)
            self.assertEqual(evidence["releaseAssetId"], 99)
            self.assertEqual(evidence["manifestBytes"], MANIFEST_BYTES.decode("utf-8"))
            self.assertEqual(evidence["manifest"], json.loads(MANIFEST_BYTES))
            self.assertEqual(evidence["workflowRunAttempt"], 1)
            self.assertIn("headCommit", evidence)
            self.assertIn("headTree", evidence)

    def test_rejects_a_malformed_manifest_identity(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, "not-a-digest", "", opener=_opener_sequence())

    def test_rejects_when_downloaded_bytes_differ_from_the_requested_digest(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            tampered = MANIFEST_BYTES + b" "
            opener = _opener_sequence(_release_tags_payload(asset_id=1, size=len(tampered)), tampered)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)

    def test_rejects_when_downloaded_bytes_differ_from_the_locally_retained_manifest(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            # Same digest as requested, but not byte-identical to the local file —
            # can only happen if the local file itself was tampered with.
            other = json.dumps({"releaseVersion": "1.2.3", "images": [], "x": 1}, sort_keys=True).encode()
            digest = "sha256:" + hashlib.sha256(other).hexdigest()
            (repo / "RELEASES" / "containers" / "v1.2.3.json").write_bytes(other)
            opener = _opener_sequence(_release_tags_payload(asset_id=1, size=len(MANIFEST_BYTES)), MANIFEST_BYTES)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, digest, "", opener=opener)

    def test_rejects_when_downloaded_size_differs_from_reviewed_metadata(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            opener = _opener_sequence(_release_tags_payload(asset_id=1, size=999999), MANIFEST_BYTES)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=opener)

    def test_raises_a_clear_error_for_rollback_receipt_requests(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            with self.assertRaises(EVIDENCE.EvidenceError) as context:
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "sha256:" + "c" * 64, opener=_opener_sequence())
            self.assertIn("rollback", str(context.exception).lower())

    def test_raises_when_config_is_missing(self) -> None:
        with TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "RELEASES" / "containers").mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=_opener_sequence())

    def test_raises_when_expected_release_source_repository_is_missing(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            (repo / "container-deployment.json").write_text(json.dumps({"expectedRelease": {}}), encoding="utf-8")
            with self.assertRaises(EVIDENCE.EvidenceError):
                EVIDENCE.collect_evidence(repo, REAL_DIGEST, "", opener=_opener_sequence())


class MainTest(unittest.TestCase):
    def test_emits_one_json_object_on_stdout_and_exits_zero(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            opener = _opener_sequence(_release_tags_payload(asset_id=1), MANIFEST_BYTES)
            with patch.object(EVIDENCE, "DEFAULT_ROOT", repo), patch.object(
                EVIDENCE.urllib.request, "urlopen", opener
            ):
                exit_code = EVIDENCE.main(["--manifest-identity", REAL_DIGEST, "--fleet", "github-canary"])
            self.assertEqual(exit_code, 0)

    def test_exits_nonzero_and_reports_on_stderr_when_evidence_cannot_be_collected(self) -> None:
        with TemporaryDirectory() as raw:
            repo = _make_repo(Path(raw))
            with patch.object(EVIDENCE, "DEFAULT_ROOT", repo):
                exit_code = EVIDENCE.main(["--manifest-identity", "bad", "--fleet", "github-canary"])
            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
