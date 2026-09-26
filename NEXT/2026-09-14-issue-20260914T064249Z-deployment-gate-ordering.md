---
date: 2026-09-14
id: 20260914T064249Z
impact: patch
title: Stop the pending deployment gate from masking shell-tests
---

The fail-closed canonical deployment readiness gate ran mid-job in `shell-tests`,
so while it stays red awaiting the owner-supplied review publisher App identities
for #197 it aborted the job before ten later contract tests executed at all —
image build check, Bubblewrap, cache inventory, GHCR retention, changelog tooling
cache, ephemeral supervisor, work-root isolation, canonical changelog, neutral CI
credentials and privileged merge callers. Order the gate last and add
`tests/deployment_gate_ordering_test.py` so the masking cannot recur. The gate
itself is unchanged and still fails closed; no generated artifact was edited and
no trust root was filled in.
