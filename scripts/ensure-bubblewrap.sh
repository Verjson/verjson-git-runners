#!/usr/bin/bash
set -euo pipefail

readonly BUBBLEWRAP_VERSION="${BUBBLEWRAP_VERSION:-0.11.1-1ubuntu0.1}"
readonly BUBBLEWRAP_ANCHOR_PATH=/etc/verjson-bubblewrap-apt-sha256.json
installed_version="$(dpkg-query -W -f='${Version}' bubblewrap 2>/dev/null || true)"

if [[ ! -x /usr/bin/bwrap || "$installed_version" != "$BUBBLEWRAP_VERSION" || ! -f /etc/verjson-bubblewrap.deb || ! -f "$BUBBLEWRAP_ANCHOR_PATH" ]]; then
  [[ -x /usr/local/bin/install-bubblewrap ]]
  BUBBLEWRAP_VERSION="$BUBBLEWRAP_VERSION" /usr/local/bin/install-bubblewrap
fi

installed_version="$(dpkg-query -W -f='${Version}' bubblewrap 2>/dev/null || true)"
if [[ ! -x /usr/bin/bwrap || "$installed_version" != "$BUBBLEWRAP_VERSION" ]]; then
  echo "bubblewrap bootstrap: /usr/bin/bwrap is unavailable" >&2
  exit 1
fi
