#!/usr/bin/env bash
# The canonical pre-credential guard bounds writes and restores the tree on failure.
set -euo pipefail
[[ $# -eq 2 ]] || exit 2
python3 - "$1" "$2" <<'PY'
import json
import re
import sys
from pathlib import Path

version, manifest_path = sys.argv[1:]
if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
    raise SystemExit("release reconciliation requires a stable version")
if manifest_path != "release-manifest.json" or Path(manifest_path).is_symlink():
    raise SystemExit("release reconciliation requires the canonical manifest path")
manifest = json.loads(Path(manifest_path).read_text())
if manifest.get("schemaVersion") != 2 or manifest.get("releaseVersion") != version:
    raise SystemExit("release manifest version does not match the dispatch")
base = [image for image in manifest["images"] if image.get("variant") == "base"]
if len(base) != 1 or base[0].get("repository") != "ghcr.io/verjson/gha-runner":
    raise SystemExit("release manifest must have exactly one canonical base")
digest = base[0].get("indexDigest")
if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
    raise SystemExit("release manifest base digest is not immutable")
reference = f"ghcr.io/verjson/gha-runner@{digest}"
paths = ["images/rust.Dockerfile", "images/node.Dockerfile", "images/python.Dockerfile",
         "images/go.Dockerfile", "Dockerfile.pwsh", "README.md"]
updates = {}
for name in paths:
    path = Path(name)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents) or not path.is_file():
        raise SystemExit(f"release input must be a regular file: {name}")
    pattern = r"(?m)^ARG VERJSON_BASE_IMAGE=ghcr\.io/verjson/gha-runner@sha256:[0-9a-f]{64}$"
    replacement = f"ARG VERJSON_BASE_IMAGE={reference}"
    if name == "README.md":
        pattern = r"(?m)^digest `ghcr\.io/verjson/gha-runner@sha256:[0-9a-f]{64}`;"
        replacement = f"digest `{reference}`;"
    updated, count = re.subn(pattern, replacement, path.read_text())
    if count != 1:
        raise SystemExit(f"release input must contain exactly one standalone base pin: {name}")
    updates[path] = updated
# Validate every input before any write; the canonical guard handles I/O failure rollback.
for path, content in updates.items():
    path.write_text(content)
PY
