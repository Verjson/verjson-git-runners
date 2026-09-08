#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
contract_cache="$(mktemp -d)"
trap 'rm -rf "$contract_cache"' EXIT
python3 - <<'PY'
import os
import re
import subprocess
from pathlib import Path
commit = os.environ.get('VERJSON_PRODUCER_DISPATCH_COMMIT', '')
if not re.fullmatch('[0-9a-f]{40}', commit):
    raise SystemExit('VERJSON_PRODUCER_DISPATCH_COMMIT must be an immutable SHA')
if subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() != commit:
    raise SystemExit('dispatch commit must match the tested checkout')
if Path('.verjson-ci/producer-plan.json').is_symlink():
    raise SystemExit('producer plan must not be a symlink')
for path in [Path('.verjson-ci'), Path('.verjson-ci/producer-evidence')]:
    if path.is_symlink():
        raise SystemExit('producer artifact directories must not be symlinks')
    path.mkdir(exist_ok=True)
for path in Path('.verjson-ci/producer-evidence').iterdir():
    if path.is_symlink() or not path.is_file():
        raise SystemExit('producer evidence must contain only regular files')
PY
checks=(
  tests/installer_migration_test.py
  tests/producer_plan_test.py
  tests/gitlab_build_config_test.py
  tests/release_reconcile_test.py
  tests/ghcr_retention_test.py
  tests/entrypoint_test.sh
  tests/setup_powershell_source_test.sh
  tests/container_release_workflow_test.sh
  scripts/container-candidate-contract.test.sh
  scripts/container-release-contract.test.sh
  tests/image_build_check_workflow_test.sh
  tests/cache_inventory_test.sh
  tests/ghcr_retention_workflow_test.sh
  tests/changelog_tool_cache_test.sh
  tests/work_root_isolation_test.sh
  scripts/changelog-contract.test.sh
  tests/neutral_ci_credentials_test.sh
  tests/privileged_merge_caller_contract_test.sh
)
for check in "${checks[@]}"; do
  case "$check" in
    *.py) python3 "$check" ;;
    scripts/changelog-contract.test.sh) VERJSON_CHANGELOG_TOOL_CACHE="$contract_cache" bash "$check" ;;
    *.sh) bash "$check" ;;
  esac
done
(cd app && go test ./...)
bash scripts/gen-adr-index.sh --check
python3 - "${checks[@]}" <<'PY'
import os
import sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from producer_plan import encode
receipt = {
    'schemaVersion': 1,
    'dispatchCommit': os.environ['VERJSON_PRODUCER_DISPATCH_COMMIT'],
    'result': 'passed',
    'checks': sys.argv[1:] + ['cd app && go test ./...', 'scripts/gen-adr-index.sh --check'],
    'excluded': [{'check': 'tests/ephemeral_supervisor_integration.sh',
                  'reason': 'requires a Docker daemon; isolated GitLab jobs have no host socket'}],
}
path = Path('.verjson-ci/producer-evidence/test-receipt.json')
if path.is_symlink():
    raise SystemExit('test receipt must not be a symlink')
path.write_bytes(encode(receipt))
PY
python3 scripts/producer_plan.py
