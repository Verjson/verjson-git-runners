---
date: 2026-09-27
id: 20260927T162307Z
impact: patch
title: Repin the AI-review caller family to the details_url-binding fix
---

`Verjson/.github`'s AI-review-authorization gate broke org-wide when a
GitHub platform behavior change made Actions-owned check runs stop honoring
a custom `details_url` (`Verjson/.github#1648`), leaving every dispatched
review stuck `in_progress` with `authorization check is not receipt-bound`.
Fixed upstream by `Verjson/.github#1649` (merged
`68b823b133dabc8d8e9f11f9ab5c179e78ae5692`, released as v3.0.1) and the
required-workflow ruleset was rotated to it, but this repository's own
generated callers (`ai-review-merge.yml`, `ai-review-label-rearm.yml`,
`ai-privileged-merge.yml`, `ai-promotion-retry.yml`) were still pinned to
the pre-fix contract SHA `645e5c23c512e57b14494b1ceb3715559900bac6` — a
fresh dispatch under the old pin still hit the bug
(`verjson-git-runners#232`, runs 36324085985/36331719246).

Regenerated all four callers at the current canonical `Verjson/.github` HEAD
(`2375c5e6b18bba33699184de15294d4541c30f89`; no contract-relevant path moved
since the fix) via `gen-ai-review-caller.sh`, `gen-ai-review-label-rearm-caller.sh`,
and `gen-privileged-merge-caller.sh`, and bumped `tests/contract_pins.json`'s
`ai-callers` and `ai-review-merge` pins to match. The new contract legitimately
adds `actions: write` and `issues: read` to the privileged-merge pair, landed
between the two pins by `Verjson/.github#1583` (ADR 0207): `actions: write`
backs a post-merge cleanup of the consumed arm-receipt artifact, and
`issues: read` backs a caller-owned read of `closingIssuesReferences` to
surface issues the terminal merge silently fails to auto-close. Updated
`tests/privileged_merge_caller_contract_test.sh`'s digest and permission
assertions accordingly, and the two hardcoded digests in
`tests/ai_review_caller_test.py`.

The `re-review` label recovery path (`ai-review-label-rearm.yml`) still has a
separate, unrelated bug filed as `Verjson/.github#1652` (a checkout step binds
the wrong repository's commit SHA); this regeneration does not fix that path,
only the standard synchronize-triggered one.
