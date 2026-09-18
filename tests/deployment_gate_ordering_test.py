#!/usr/bin/env python3
"""The pending deployment readiness gate must not mask the rest of shell-tests.

`scripts/container-deployment-contract.test.sh` fails by design until the owner
supplies the review publisher App identities tracked in #197. A GitHub Actions job
stops at its first failing step, so while that gate is red every step ordered after
it is silently never executed. Keeping it last preserves the signal from every
other contract test for the whole life of the draft.
"""
import sys
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github/workflows/test.yml"
PENDING_GATE = "scripts/container-deployment-contract.test.sh"


def main() -> int:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["shell-tests"]["steps"]
    commands = [step.get("run", "") for step in steps]
    gate_indexes = [i for i, run in enumerate(commands) if PENDING_GATE in run]

    assert gate_indexes, f"{PENDING_GATE} is not wired into shell-tests"
    assert len(gate_indexes) == 1, f"{PENDING_GATE} is wired more than once"
    assert gate_indexes[0] == len(steps) - 1, (
        f"{PENDING_GATE} must be the last shell-tests step; it currently masks "
        f"{len(steps) - 1 - gate_indexes[0]} later step(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
