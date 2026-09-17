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
workflow_text="$(<"${workflow}")"

# The image build already proves the image *it builds* satisfies the Bubblewrap contract.
# What nothing asserted is that the image the shared lane actually *delivers* does, which
# is how a released runner three weeks behind that contract reached consumers as a red
# `main` instead of a red check here. The probe must therefore execute the very script the
# image build runs, never a re-implementation that can drift away from it.
[[ "${workflow_text}" == *'scripts/bubblewrap-image-contract.py'* ]] \
  || fail "the lane probe does not execute the shared Bubblewrap image contract"

# Routing. `runs-on` lives in a file a pull request can edit, so the probe must resolve the
# lane the same way every other verJSON workflow does — through the organization lane
# variable, never a literal label. And uniquely among those workflows it must carry no
# hosted fallback tail: the one job whose purpose is to measure the self-hosted lane would
# otherwise report a hosted runner's unrelated conformance as this lane's success whenever
# the variable is missing. A missing variable has to fail it.
runs_on="$(sed -n 's/^ *runs-on: *//p' "${workflow}")"
[[ -n "${runs_on}" ]] || fail "the lane probe declares no runs-on"
[[ "${runs_on}" == *'fromJSON(vars.VERJSON_RUNNER_DEFAULT'* ]] \
  || fail "the lane probe does not resolve the shared lane variable: ${runs_on}"
[[ "${runs_on}" != *'ubuntu-'* && "${runs_on}" != *'self-hosted'* ]] \
  || fail "the lane probe hardcodes a runner selector: ${runs_on}"
[[ "${runs_on}" != *'||'* ]] \
  || fail "the lane probe falls back off the lane it exists to measure: ${runs_on}"

# A probe that cannot redden reports nothing. Drift is the finding, not an inconvenience.
[[ "${workflow_text}" != *'continue-on-error'* ]] \
  || fail "the lane probe tolerates its own failure"
