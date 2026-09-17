#!/usr/bin/bash
set -euo pipefail

readonly BUBBLEWRAP_PIN_PATH="${BUBBLEWRAP_PIN_PATH:-/usr/local/share/verjson-bubblewrap-pin.json}"
readonly BUBBLEWRAP_ANCHOR_PATH=/etc/verjson-bubblewrap-apt-sha256.json

# Resolved per architecture for the reason install-bubblewrap documents: Ubuntu moves one
# architecture ahead of the other, so the exact pin lives per architecture in the checked-in
# descriptor. This block is byte-identical to the installer's and is held so by
# tests/bubblewrap_image_contract_test.py.
architecture="$(dpkg --print-architecture)"
BUBBLEWRAP_VERSION="$(
  python3 - "$BUBBLEWRAP_PIN_PATH" "$architecture" <<'PY'
import json
import re
import sys

path, architecture = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as descriptor:
    pin = json.load(descriptor)
if pin.get("package") != "bubblewrap":
    raise SystemExit(f"{path}: not a Bubblewrap pin descriptor")
record = pin.get("architectures", {}).get(architecture)
if not isinstance(record, dict):
    raise SystemExit(f"{path}: no Bubblewrap pin for architecture {architecture}")
version = record.get("version")
if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9.+~:-]+", version):
    raise SystemExit(f"{path}: Bubblewrap pin for {architecture} has no exact version")
print(version)
PY
)"
readonly BUBBLEWRAP_VERSION
[[ -n "$BUBBLEWRAP_VERSION" ]]

installed_version="$(dpkg-query -W -f='${Version}' bubblewrap 2>/dev/null || true)"

if [[ ! -x /usr/bin/bwrap || "$installed_version" != "$BUBBLEWRAP_VERSION" || ! -f /etc/verjson-bubblewrap.deb || ! -f "$BUBBLEWRAP_ANCHOR_PATH" ]]; then
  [[ -x /usr/local/bin/install-bubblewrap ]]
  /usr/local/bin/install-bubblewrap
fi

installed_version="$(dpkg-query -W -f='${Version}' bubblewrap 2>/dev/null || true)"
if [[ ! -x /usr/bin/bwrap || "$installed_version" != "$BUBBLEWRAP_VERSION" ]]; then
  echo "bubblewrap bootstrap: /usr/bin/bwrap is unavailable" >&2
  exit 1
fi
