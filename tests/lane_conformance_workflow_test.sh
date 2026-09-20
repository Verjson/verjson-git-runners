#!/usr/bin/env bash
# shellcheck disable=SC2016 # GitHub expressions below are intentional literals.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workflow="${1:-${root}/.github/workflows/lane-conformance.yml}"

fail() {
  echo "lane-conformance contract: $*" >&2
  exit 1
}

[[ -f "${workflow}" ]] || fail "workflow not found: ${workflow}"

bubblewrap_job="$(awk '
  /^[[:space:]]*bubblewrap:[[:space:]]*$/ {
    in_job = 1
    job_indent = match($0, /[^[:space:]]/) - 1
    print
    next
  }
  in_job {
    if ($0 !~ /^[[:space:]]*$/ && match($0, /[^[:space:]]/) - 1 <= job_indent) exit
    print
  }
' "${workflow}")"
[[ -n "${bubblewrap_job}" ]] || fail "bubblewrap job not found"

# Image builds prove the image they build satisfies the contract. This probe must
# run the same checker in the active bubblewrap job on the delivered lane.
probe_run="$(awk '
  /^[[:space:]]+run:[[:space:]]*python3 scripts\/bubblewrap-image-contract\.py[[:space:]]*$/ {
    sub(/^[[:space:]]+run:[[:space:]]*/, "")
    print
    exit
  }
' <<<"${bubblewrap_job}")"
[[ "${probe_run}" == 'python3 scripts/bubblewrap-image-contract.py' ]] \
  || fail "the bubblewrap job does not run the shared image contract"

dispatch_trigger="$(awk '
  /^[[:space:]]*on:[[:space:]]*$/ { in_triggers = 1; next }
  in_triggers && /^[^[:space:]#]/ { exit }
  in_triggers && /^[[:space:]]+workflow_dispatch:[[:space:]]*($|#)/ { print; exit }
' "${workflow}")"
[[ -z "${dispatch_trigger}" ]] \
  || fail "the self-hosted lane probe must not dispatch a selected branch"

bubblewrap_guard="$(awk '
  /^[[:space:]]+if:[[:space:]]*/ {
    sub(/^[[:space:]]+if:[[:space:]]*/, "")
    print
    exit
  }
' <<<"${bubblewrap_job}")"
[[ "${bubblewrap_guard}" == "github.ref == 'refs/heads/main'" ]] \
  || fail "the bubblewrap job can run code from a non-main ref"

# Keep the scheduled self-hosted observation job on the reviewed default branch.
checkout_ref="$(awk '
  /^[[:space:]]*-[[:space:]]*uses:[[:space:]]*actions\/checkout@/ { in_checkout = 1; next }
  in_checkout && /^[[:space:]]*-[[:space:]]/ { exit }
  in_checkout && /^[[:space:]]+ref:[[:space:]]*/ {
    sub(/^[[:space:]]+ref:[[:space:]]*/, "")
    print
    exit
  }
' <<<"${bubblewrap_job}")"
[[ "${checkout_ref}" == main ]] \
  || fail "the bubblewrap job does not explicitly check out main"

# This job measures the shared lane; do not silently route to a hosted fallback.
runs_on="$(awk '
  /^[[:space:]]+runs-on:[[:space:]]*/ {
    sub(/^[[:space:]]+runs-on:[[:space:]]*/, "")
    print
    exit
  }
' <<<"${bubblewrap_job}")"
[[ -n "${runs_on}" ]] || fail "the bubblewrap job declares no runs-on"
[[ "${runs_on}" == *'fromJSON(vars.VERJSON_RUNNER_DEFAULT'* ]] \
  || fail "the bubblewrap job does not resolve the shared lane variable: ${runs_on}"
[[ "${runs_on}" != *'ubuntu-'* && "${runs_on}" != *'self-hosted'* ]] \
  || fail "the bubblewrap job hardcodes a runner selector: ${runs_on}"
[[ "${runs_on}" != *'||'* ]] \
  || fail "the bubblewrap job falls back off the lane it exists to measure: ${runs_on}"

# A probe cannot report green while tolerating its own failure.
! grep -Eq '^[[:space:]]+continue-on-error:' <<<"${bubblewrap_job}" \
  || fail "the lane probe tolerates its own failure"

# Control the job scoping: a sibling job cannot provide the expected probe.
fixture_dir="$(mktemp -d)"
trap 'rm -rf "${fixture_dir}"' EXIT
cat >"${fixture_dir}/sibling-only.yml" <<'EOF'
on:
  schedule:
    - cron: '37 */6 * * *'
jobs:
  bubblewrap:
    if: github.ref == 'refs/heads/main'
    runs-on: fromJSON(vars.VERJSON_RUNNER_DEFAULT)
    steps:
      - uses: actions/checkout@0000000000000000000000000000000000000000
        with:
          ref: main
      - run: echo missing probe
  other:
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - run: python3 scripts/bubblewrap-image-contract.py
EOF
if "${BASH_SOURCE[0]}" "${fixture_dir}/sibling-only.yml" >"${fixture_dir}/result" 2>&1; then
  fail "a sibling job satisfied the bubblewrap probe contract"
fi
grep -Fq "the bubblewrap job does not run the shared image contract" "${fixture_dir}/result" \
  || fail "the sibling-job control failed for an unexpected reason"
