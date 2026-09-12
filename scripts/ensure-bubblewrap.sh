#!/usr/bin/bash
set -euo pipefail

readonly BUBBLEWRAP_VERSION="${BUBBLEWRAP_VERSION:-0.11.1-1ubuntu0.1}"
installed_version="$(dpkg-query -W -f='${Version}' bubblewrap 2>/dev/null || true)"

if [[ ! -x /usr/bin/bwrap || "$installed_version" != "$BUBBLEWRAP_VERSION" || ! -f /etc/verjson-bubblewrap.deb ]]; then
  apt-get update
  apt-get install -y --no-install-recommends "bubblewrap=${BUBBLEWRAP_VERSION}"
  cd /tmp
  apt-get download "bubblewrap=${BUBBLEWRAP_VERSION}"
  package_archive="$(find /tmp -maxdepth 1 -type f -name 'bubblewrap_*.deb' -print -quit)"
  [[ -n "$package_archive" ]]
  install -m 0444 "$package_archive" /etc/verjson-bubblewrap.deb
  rm -f "$package_archive"
  rm -rf /var/lib/apt/lists/*
fi

installed_version="$(dpkg-query -W -f='${Version}' bubblewrap 2>/dev/null || true)"
if [[ ! -x /usr/bin/bwrap || "$installed_version" != "$BUBBLEWRAP_VERSION" ]]; then
  echo "bubblewrap bootstrap: /usr/bin/bwrap is unavailable" >&2
  exit 1
fi
