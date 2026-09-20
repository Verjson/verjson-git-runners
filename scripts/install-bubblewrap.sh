#!/usr/bin/bash
set -euo pipefail

readonly BUBBLEWRAP_PIN_PATH="${BUBBLEWRAP_PIN_PATH:-/usr/local/share/verjson-bubblewrap-pin.json}"
readonly BUBBLEWRAP_ANCHOR_PATH=/etc/verjson-bubblewrap-apt-sha256.json
package_directory="$(mktemp -d)"
trap 'rm -rf "$package_directory"' EXIT

# Ubuntu publishes each architecture independently, so one shared version pin is not a
# property the archive guarantees: resolute-updates served bubblewrap 0.11.1-1ubuntu0.2 on
# arm64 while amd64 was still on 0.11.1-1ubuntu0.1. The pin therefore stays exact but is
# resolved per architecture from the checked-in descriptor, which is the single source the
# immutable provenance is copied from. A missing record is fatal, never a floating version.
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
if not isinstance(version, str) or not re.fullmatch(r"[0-9][A-Za-z0-9.+~:-]*", version):
    raise SystemExit(f"{path}: Bubblewrap pin for {architecture} has no exact version")
print(version)
PY
)"
readonly BUBBLEWRAP_VERSION
[[ -n "$BUBBLEWRAP_VERSION" ]]

# apt's signed Packages metadata supplies the package checksum independently of
# the repository source and its checked-in provenance descriptor.
apt-get update
(
  cd "$package_directory"
  apt-get download "bubblewrap=${BUBBLEWRAP_VERSION}"
)
mapfile -t package_archives < <(find "$package_directory" -maxdepth 1 -type f -name 'bubblewrap_*.deb' -print)
[[ "${#package_archives[@]}" -eq 1 ]]
package_archive="${package_archives[0]}"
expected_sha256="$(apt-cache show "bubblewrap=${BUBBLEWRAP_VERSION}" | awk -F': ' '$1 == "SHA256" && !found { print $2; found=1 }')"
[[ "$expected_sha256" =~ ^[0-9a-f]{64}$ ]]
printf '%s  %s\n' "$expected_sha256" "$package_archive" | sha256sum -c -
[[ "$(dpkg-deb -f "$package_archive" Package)" == bubblewrap ]]
[[ "$(dpkg-deb -f "$package_archive" Version)" == "$BUBBLEWRAP_VERSION" ]]
[[ "$(dpkg-deb -f "$package_archive" Architecture)" == "$architecture" ]]

# Maintainer scripts run only after the archive has passed the authenticated
# repository checksum and exact package metadata checks.
apt-get install -y --no-install-recommends "$package_archive"
install -m 0444 "$package_archive" /etc/verjson-bubblewrap.deb
printf '{"package":"bubblewrap","version":"%s","architecture":"%s","sha256":"%s"}\n' \
  "$BUBBLEWRAP_VERSION" "$architecture" "$expected_sha256" \
  > "$package_directory/anchor.json"
install -m 0444 "$package_directory/anchor.json" "$BUBBLEWRAP_ANCHOR_PATH"
rm -rf /var/lib/apt/lists/*
