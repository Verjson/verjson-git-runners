#!/usr/bin/env bash
# Opt-in local image behavior proof. Pull/provenance validation is a separate receipt.
set -euo pipefail
image="${1:?usage: gitlab_build_image_test.sh ghcr.io/verjson/gha-runner@sha256:<digest>}"
[[ "$image" =~ ^ghcr\.io/verjson/gha-runner(-node|-python|-go|-rust|-pwsh)?@sha256:[a-f0-9]{64}$ ]] || exit 2
docker run --rm --pull never --network none --user 1001:1001 \
  --cap-drop ALL --security-opt no-new-privileges --memory 1g --cpus 1 \
  --entrypoint /bin/bash "$image" -euc '
    test "$(id -u)" = 1001
    test ! -S /var/run/docker.sock
    test -w /tmp
    test -n "$(command -v git)"
    test -n "$(command -v bash)"
    if sudo -n true 2>/dev/null; then echo "sudo escalation unexpectedly succeeded" >&2; exit 1; fi
    if ps -eo args | grep -E "[R]unner.Listener|[/]entrypoint.sh"; then exit 1; fi
    printf "GitLab shell contract passed: uid=%s; sudo denied; no GitHub listener\n" "$(id -u)"
  '
