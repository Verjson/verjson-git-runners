#!/usr/bin/env python3
"""Behavioral tests for scripts/runner-deployment-probe.py.

Like the evidence adapter, this runs in the controller's stripped subprocess
sandbox (PATH, LANG, LC_ALL, TMPDIR, SSL_CERT_FILE, SSL_CERT_DIR only) — no
credential of any kind reaches it, so it cannot itself query GitHub's
self-hosted-runners API (confirmed unauthenticated-inaccessible even for a
public repository, unlike releases) or reach the target host over SSH. The
real, cryptographically verified post-update check already happened in the
controller's own privileged process before this ever runs
(ProcessAdapter.update_runner's host-export call). This adapter is therefore a
structural sanity check on its own input, not an independent health probe;
see Verjson/verjson-git-runners#223.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "runner-deployment-probe.py"
SPEC = importlib.util.spec_from_file_location("runner_deployment_probe", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class ProbeRunnerTest(unittest.TestCase):
    def test_reports_the_exact_requested_runner_as_passed(self) -> None:
        result = PROBE.probe_runner("gha-deployment-canary", 60)
        self.assertEqual(result, {"routedRunner": "gha-deployment-canary", "outcome": "passed"})

    def test_rejects_a_runner_name_outside_the_reviewed_syntax(self) -> None:
        with self.assertRaises(PROBE.ProbeError):
            PROBE.probe_runner("../etc/passwd", 60)

    def test_rejects_an_empty_runner_name(self) -> None:
        with self.assertRaises(PROBE.ProbeError):
            PROBE.probe_runner("", 60)

    def test_rejects_a_non_positive_timeout(self) -> None:
        with self.assertRaises(PROBE.ProbeError):
            PROBE.probe_runner("gha-deployment-canary", 0)


class MainTest(unittest.TestCase):
    def test_emits_one_json_object_matching_the_requested_runner(self) -> None:
        import io
        import contextlib

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = PROBE.main(["--runner", "gha-deployment-canary", "--timeout-seconds", "60"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(buffer.getvalue()),
            {"routedRunner": "gha-deployment-canary", "outcome": "passed"},
        )

    def test_exits_nonzero_and_reports_on_stderr_for_an_invalid_runner_name(self) -> None:
        exit_code = PROBE.main(["--runner", "", "--timeout-seconds", "60"])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
