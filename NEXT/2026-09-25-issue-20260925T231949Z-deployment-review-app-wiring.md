---
date: 2026-09-25
id: 20260925T231949Z
impact: patch
title: Wire real review and host-evidence authority into the deployment adopter
---

`container-deployment.json` named the code/security/AI review Apps and the
host-evidence App only as `null`; all four now exist
(`runner-deploy-code-review`, `runner-deploy-security-review`,
`runner-deploy-ai-review`, `runner-host-evidence`) and their real `appId` /
`installationId` values are wired in, along with the AI review's required
`sourceAppId`/`sourceCheckName` binding to the existing authorization-arm
check. The three `runner-deploy-*-review-publisher` environments the
canonical producer validates (`protected_branches: true`,
`custom_branch_policies: false`, one `branch_policy` rule) now exist on this
repository.

The generated deployment, review, and host-evidence-authority artifacts are
regenerated together from the current canonical contract
`22039a2e8d19339f36654323594743e8fd5031a1`, and `container-deployment-review-producer.yml`
/ `container-deployment.yml` are now registered in this repository's hub-caller
family test and `tests/contract_pins.json` — the prior pin predated both a
security fix to the review-producer workflow and the host-evidence contract
this branch's own ADR 0015 already depends on, and the caller test had no
entry for either callee.

Merging current `main` surfaced an ADR number collision between this branch's
pre-existing 0013/0014 and `main`'s newly merged 0013; this branch's ADRs are
renumbered to 0014/0015 with the generated index regenerated, not hand-edited.

Not done here: `scripts/runner-deployment-evidence.py` and
`scripts/runner-deployment-probe.py`, the adapters `evidenceCommand` /
`probeCommand` name, do not exist yet, so the contract test still fails on
their absence — this predates this change and is tracked separately.
