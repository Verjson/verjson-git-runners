#!/usr/bin/env python3
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = ["images/rust.Dockerfile", "images/node.Dockerfile", "images/python.Dockerfile",
         "images/go.Dockerfile", "Dockerfile.pwsh", "README.md"]


class ReleaseReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in PATHS + ["scripts/release-reconcile.sh"]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.manifest = json.loads((ROOT / "RELEASES/containers/v0.2.1.json").read_text())
        self.manifest["releaseVersion"] = "999.0.0"
        self.manifest["images"][0]["indexDigest"] = "sha256:" + "a" * 64

    def run_hook(self, version="999.0.0", manifest_path="release-manifest.json"):
        (self.root / "release-manifest.json").write_text(json.dumps(self.manifest))
        return subprocess.run([str(self.root / "scripts/release-reconcile.sh"), version, manifest_path],
                              cwd=self.root, capture_output=True, text=True)

    def snapshot(self):
        return {name: (self.root / name).read_bytes() for name in PATHS}

    def test_all_five_defaults_and_documentation_follow_manifest_idempotently(self):
        self.assertEqual(self.run_hook().returncode, 0)
        after = self.snapshot()
        for content in after.values():
            self.assertIn(("sha256:" + "a" * 64).encode(), content)
        self.assertEqual(self.run_hook().returncode, 0)
        self.assertEqual(self.snapshot(), after)

    def test_invalid_manifest_never_changes_release_inputs(self):
        original = copy.deepcopy(self.manifest)
        for field, value in [("schemaVersion", 1), ("releaseVersion", "0.2.1"),
                             ("images", []), ("images", [original["images"][0]] * 2)]:
            with self.subTest(field=field, value=value):
                self.manifest = copy.deepcopy(original)
                self.manifest[field] = value
                before = self.snapshot()
                self.assertNotEqual(self.run_hook().returncode, 0)
                self.assertEqual(self.snapshot(), before)
        for field, value in [("repository", "ghcr.io/attacker/base"), ("indexDigest", "latest")]:
            self.manifest = copy.deepcopy(original)
            self.manifest["images"][0][field] = value
            before = self.snapshot()
            self.assertNotEqual(self.run_hook().returncode, 0)
            self.assertEqual(self.snapshot(), before)

    def test_missing_or_duplicate_last_pin_is_rejected_before_any_write(self):
        path = self.root / "README.md"
        original = path.read_text()
        for content in ["no pin", original + "\n" + original]:
            path.write_text(content)
            before = self.snapshot()
            self.assertNotEqual(self.run_hook().returncode, 0)
            self.assertEqual(self.snapshot(), before)

    def test_symlink_input_cannot_redirect_a_write(self):
        path = self.root / "README.md"
        target = self.root / "outside.md"
        path.rename(target)
        path.symlink_to(target)
        before = target.read_bytes()
        self.assertNotEqual(self.run_hook().returncode, 0)
        self.assertEqual(target.read_bytes(), before)

    def test_manifest_path_and_dispatch_version_are_bounded(self):
        for version, path in [("v999.0.0", "release-manifest.json"),
                              ("0999.0.0", "release-manifest.json"),
                              ("999.0.0", "../release-manifest.json")]:
            before = self.snapshot()
            self.assertNotEqual(self.run_hook(version, path).returncode, 0)
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
