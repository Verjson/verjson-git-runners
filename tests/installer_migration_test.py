#!/usr/bin/env python3
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallerMigrationTest(unittest.TestCase):
    def test_new_install_clones_gitlab_and_preserves_launcher_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / "bin"
            binaries.mkdir()
            git = binaries / "git"
            git.write_text("""#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$INSTALLER_GIT_LOG"
if [ "$1" = clone ]; then
    target="${@: -1}"
    mkdir -p "$target/.git"
    printf '#!/usr/bin/env bash\\nprintf "%%s\\n" "$*" > "$INSTALLER_BOOT_LOG"\\n' > "$target/bootstrap.sh"
fi
""")
            git.chmod(0o755)
            env = dict(os.environ, PATH=f"{binaries}:{os.environ['PATH']}",
                       GHA_DIR=str(root / "existing-compatible-directory"),
                       GHA_REF="main", INSTALLER_GIT_LOG=str(root / "git.log"),
                       INSTALLER_BOOT_LOG=str(root / "bootstrap.log"))
            result = subprocess.run(["bash", str(ROOT / "install.sh"), "--no-run"],
                                    env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, start_new_session=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("https://git.159-195-78-163.nip.io/Verjson/verjson-git-runners.git", (root / "git.log").read_text())
            self.assertTrue((root / "existing-compatible-directory/.git").is_dir())
            self.assertIn("--no-run", (root / "bootstrap.log").read_text())


if __name__ == "__main__":
    unittest.main()
