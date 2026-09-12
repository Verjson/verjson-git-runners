#!/usr/bin/env bash
set -euo pipefail

if [[ ! -x /usr/bin/bwrap ]]; then
  apt-get update
  apt-get install -y --no-install-recommends bubblewrap
  rm -rf /var/lib/apt/lists/*
fi

if [[ ! -x /usr/bin/bwrap ]]; then
  echo "bubblewrap bootstrap: /usr/bin/bwrap is unavailable" >&2
  exit 1
fi
