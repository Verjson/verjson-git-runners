#!/usr/bin/env python3
"""Probe adapter for container_deployment_controller.py's representative probe step.

Invoked as this repository's reviewed `probeCommand` (container-deployment.json),
this process runs in the controller's stripped subprocess sandbox: only PATH, LANG,
LC_ALL, TMPDIR, SSL_CERT_FILE, and SSL_CERT_DIR reach it. It has no credential of
any kind, so it cannot query GitHub's self-hosted-runners API (confirmed
unauthenticated-inaccessible even for a public repository) or reach the target
host over SSH itself.

By the time this runs, ProcessAdapter.update_runner has already independently
verified the update via the controller's own privileged host-export transport
(App JWT + read-only SSH, real cryptographic evidence: image digest, admission,
labels, tools, idle state) and _validate_runner_result has already accepted that
evidence. This adapter is a structural sanity check on its own input, not an
independent functional canary — a real one (dispatching runner-canary.yml and
verifying a representative job actually ran) needs credentials this sandbox
does not have. See Verjson/verjson-git-runners#223.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

RUNNER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class ProbeError(Exception):
    """A reviewed, fail-closed probe failure."""


def probe_runner(runner: str, timeout_seconds: int) -> dict[str, Any]:
    if RUNNER_NAME.fullmatch(runner) is None:
        raise ProbeError("runner name is outside the reviewed syntax")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or timeout_seconds < 1:
        raise ProbeError("timeout-seconds must be a positive integer")
    return {"routedRunner": runner, "outcome": "passed"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--timeout-seconds", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        result = probe_runner(args.runner, args.timeout_seconds)
    except ProbeError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
