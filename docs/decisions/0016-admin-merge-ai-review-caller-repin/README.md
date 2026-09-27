# 0016 — Admin-merge #233 past a structurally-unresolvable AI review authorization check

- **Date:** 2026-09-27
- **Status:** Accepted
- **Issue:** [#232](https://github.com/Verjson/verjson-git-runners/pull/232), [#197](https://github.com/Verjson/verjson-git-runners/issues/197), [Verjson/.github#1648](https://github.com/Verjson/.github/issues/1648), [Verjson/.github#1649](https://github.com/Verjson/.github/pull/1649)
- **Category:** CI trust boundary, repository-ruleset override (sensitive class)

## Context

`Verjson/.github#1648` broke the org-wide "AI review authorization" gate: GitHub
stopped honoring a custom `details_url` on Actions-owned check runs, so every
dispatched review failed preflight with `authorization check is not
receipt-bound` and the check stayed `in_progress` forever (the finalizer's own
fail-safe also refuses to force-terminalize a check it cannot prove it owns).
Fixed upstream by `Verjson/.github#1649` (merged `68b823b`, released v3.0.1).

This repository's own generated AI-review caller family
(`ai-review-merge.yml`, `ai-review-label-rearm.yml`, `ai-privileged-merge.yml`,
`ai-promotion-retry.yml`) was still pinned to the pre-fix contract SHA, so PR
`#232` (the unrelated container-deployment secrets-inherit fix this session
was actually sent to deliver) could not obtain a working review. PR `#233`
regenerated all four callers at the current canonical `Verjson/.github` HEAD to
fix this for good.

`#233` could not validate itself before merging: `gate-rearm.yml` dispatches
`ai-review-merge.yml` via `gh workflow run ... --ref "$DEFAULT_BRANCH"`, which
always runs the workflow file as it exists on `main` — not on the PR branch.
Every dispatch attempted against `#233`'s own head therefore ran the *old*,
still-broken reusable workflow (confirmed in the job logs: `Uses:
.../ai-review-merge.yml@645e5c23...`, the pre-fix SHA), reproducing the exact
`#1648` failure regardless of what `#233` changed. This is the same
self-referential bootstrap `Verjson/.github#1649` itself had to break via an
admin merge on the canonical repo.

This session's own `scripts/assert-mergeable-head.sh` Gate C correctly refused
to certify `#233` mergeable while any non-required check (including "AI review
authorization") was pending — a deliberately conservative default. Given the
diagnosis above, that check could never resolve favorably before merge, by
construction, regardless of `#233`'s actual correctness.

## Decision

The user explicitly authorized overriding Gate C for `#233` specifically,
after review of:

- An independent adversarial `code-reviewer` pass that byte-verified all four
  regenerated files against the canonical generator's live output at the
  pinned SHA, confirmed the one permission widening (`actions: write`,
  `issues: read` on the privileged-merge pair) was upstream-authorized
  (`Verjson/.github#1583`, ADR 0207) rather than introduced by this PR, and
  mutation-tested that the digest pins are non-vacuous.
- Both status checks actually required by this repository's branch-protection
  ruleset (`changelog / validate`, `shell-tests`) green on the exact head
  merged (`d161e54db867e6a36644e84b8480f14a6dcffce2`).
- The stuck "AI review authorization" check being a proven structural artifact
  of the dispatch mechanism described above, not a signal about this diff.

Merged via `gh pr merge --squash --admin --match-head-commit
d161e54db867e6a36644e84b8480f14a6dcffce2` (merge SHA
`73bd9c08b3353123c3fc86ddd94fcb925c24aa26`).

## Consequences

- `#232` can now retry its own dispatch against the fixed, merged
  `ai-review-merge.yml` on `main` and obtain a real review.
- This override is specific to `#233`'s proven bootstrap circumstance. It does
  not relax Gate C generally: a future PR with a stuck non-required check
  still requires the same evidence (independent review, green required
  checks, and a proven — not assumed — reason the check cannot resolve) before
  requesting the same kind of exception.
- `Verjson/.github#1652` (the `re-review` label path's separate checkout bug)
  and `Verjson/.github#1643` (a failed preflight never reaches a terminal
  `conclusion`, reproduced on both `#232`'s and `#233`'s stuck checks;
  corroborating evidence posted, closure by `#1649` not yet confirmed) remain
  open upstream defects. Neither blocks this decision but both make the next
  occurrence of this exact bootstrap harder to recover from without another
  admin override.
