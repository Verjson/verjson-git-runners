#!/usr/bin/bash
set -euo pipefail

readonly BUBBLEWRAP_VERSION="${BUBBLEWRAP_VERSION:-0.11.1-1ubuntu0.1}"
readonly BUBBLEWRAP_ANCHOR_PATH=/etc/verjson-bubblewrap-apt-sha256.json
package_directory="$(mktemp -d)"
trap 'rm -rf "$package_directory"' EXIT

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
expected_sha256="$(apt-cache show "bubblewrap=${BUBBLEWRAP_VERSION}" | awk -F': ' '$1 == "SHA256" { print $2; exit }')"
[[ "$expected_sha256" =~ ^[0-9a-f]{64}$ ]]
printf '%s  %s\n' "$expected_sha256" "$package_archive" | sha256sum -c -
[[ "$(dpkg-deb -f "$package_archive" Package)" == bubblewrap ]]
[[ "$(dpkg-deb -f "$package_archive" Version)" == "$BUBBLEWRAP_VERSION" ]]
[[ "$(dpkg-deb -f "$package_archive" Architecture)" == "$(dpkg --print-architecture)" ]]

# Maintainer scripts run only after the archive has passed the authenticated
# repository checksum and exact package metadata checks.
apt-get install -y --no-install-recommends "$package_archive"
install -m 0444 "$package_archive" /etc/verjson-bubblewrap.deb
printf '{"package":"bubblewrap","version":"%s","architecture":"%s","sha256":"%s"}\n' \
  "$BUBBLEWRAP_VERSION" "$(dpkg --print-architecture)" "$expected_sha256" \
  > "$package_directory/anchor.json"
install -m 0444 "$package_directory/anchor.json" "$BUBBLEWRAP_ANCHOR_PATH"
rm -rf /var/lib/apt/lists/*
