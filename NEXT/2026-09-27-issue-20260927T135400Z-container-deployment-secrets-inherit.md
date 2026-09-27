---
date: 2026-09-27
id: 20260927T135400Z
refs: 197
impact: patch
title: Regenerate container-deployment callers to inherit the production secret context
---

The generated container-deployment callers bound the caller's `production`
environment for approval gating but never delivered that environment's
secrets to the reusable workflow — GitHub Actions requires `secrets: inherit`
(or an explicit `secrets:` map) on the calling job regardless of any
`environment:` binding. All four `RUNNER_HOST_EVIDENCE_*` variables arrived
empty in a real dispatched run
(https://github.com/Verjson/verjson-git-runners/actions/runs/36279086275),
reported upstream on `Verjson/.github#1451` and fixed there by `.github#1625`
(merged as `461e218c36d86efe29a22c29a3fc5b29c4f200ae`; see ADR 0198's
2026-09-26 amendment for the widened-inheritance trade-off).

Regenerated the full caller set —
`.github/workflows/container-deployment.yml`,
`container-deployment-{code,security,ai}-review.yml`,
`container-deployment-review-producer.yml`,
`container_deployment_{controller,transport,preflight,review_producer}.py`,
`deployment-receipt.schema.json`, and
`scripts/container-deployment-contract.test.sh` — at the current canonical
`Verjson/.github` HEAD (`737250a776a7990b5874e8f3a4c50e1c6d3d683c`; no
contract-relevant path moved between the reported merge SHA and this HEAD)
via `Verjson/.github/scripts/gen-container-deployment.sh`, and bumped
`tests/contract_pins.json`'s `container-deployment` pin to match. The
regenerated contract test now requires exactly one `secrets: inherit` line
per reusable edge and still rejects any named secret, `secrets.` reference,
`RUNNER_HOST_EVIDENCE_` name, or `environment:` binding in the caller.
