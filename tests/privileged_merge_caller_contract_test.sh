#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
primary="${root}/.github/workflows/ai-privileged-merge.yml"
retry="${root}/.github/workflows/ai-promotion-retry.yml"

printf '%s  %s\n' \
  '153b072bf5ea4f5ed4fdf1e3b03a6a4f5b9eb32d2192f7105baa9cf25b2455f4' "${primary}" \
  '059291cd630e3a23ef3b7766151b164ef26e56dd4618b76aeeb6cd2a39d2e5ec' "${retry}" \
  | sha256sum --check --strict >/dev/null

python3 - "${primary}" "${retry}" "${root}/tests/contract_pins.json" <<'PY'
import json
import sys
import yaml

primary_text = open(sys.argv[1], encoding="utf-8").read()
retry_text = open(sys.argv[2], encoding="utf-8").read()
primary = yaml.safe_load(primary_text)
retry = yaml.safe_load(retry_text)
# Shared with tests/ai_review_caller_test.py: one pin per family, one file.
contract = json.loads(open(sys.argv[3], encoding="utf-8").read())["ai-callers"]
permissions = {
    "actions": "read",
    "checks": "read",
    "contents": "read",
    "pull-requests": "read",
}
required_checks = [
    {
        "name": "shell-tests",
        "app_id": 15368,
        "workflow_id": 319611670,
        "workflow_path": ".github/workflows/test.yml",
    },
    {
        "name": "changelog / validate",
        "app_id": 15368,
        "workflow_id": 325336751,
        "workflow_path": ".github/workflows/changelog.yml",
    },
]

assert primary["permissions"] == permissions
assert retry["permissions"] == permissions
assert primary["jobs"]["privileged_merge"]["uses"] == (
    f"Verjson/.github/.github/workflows/ai-privileged-merge.yml@{contract}"
)
assert retry["jobs"]["retry"]["uses"] == (
    f"Verjson/.github/.github/workflows/ai-promotion-retry.yml@{contract}"
)
# Custody moved into the callee under ADR 0166/0180: the merge App private key
# is an environment secret of `merge-app`, not a repository secret, so a caller
# cannot name it in `secrets:` at all — it is not in scope where the caller
# runs. The control that replaced the explicit grant is the environment
# binding, so assert that instead of asserting the grant is gone.
assert primary["jobs"]["privileged_merge"]["secrets"] == "inherit"
assert retry["jobs"]["retry"]["secrets"] == "inherit"
assert primary["jobs"]["privileged_merge"]["with"]["merge_environment"] == "merge-app"
assert retry["jobs"]["retry"]["with"]["merge_environment"] == "merge-app"
assert json.loads(primary["jobs"]["privileged_merge"]["with"]["required_checks"]) == required_checks
assert json.loads(retry["jobs"]["retry"]["with"]["required_checks"]) == required_checks
for workflow, source in ((primary, primary_text), (retry, retry_text)):
    assert "ORG_ADMIN_TOKEN" not in source
    assert "MERGE_APP_PRIVATE_KEY" not in source
    assert "generated-artifacts / validate" not in source
    assert "write" not in workflow["permissions"].values()
PY

echo "privileged merge generated caller contract passed"
