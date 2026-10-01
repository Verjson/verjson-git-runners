---
date: 2026-10-01
issue: 235
impact: patch
title: Adopt the merged lifecycle re-arm caller contract
---

Regenerated the AI review gate, lifecycle, label, authorization-dispatch,
privileged-merge, and promotion-retry callers from the canonical
`Verjson/.github` contract at `2d1ea177fdafe361f9369526cbab8bc05f9e476d`.
The gate now exposes the required environment input used by the lifecycle and
label callers, with each re-arm caller owning only its assigned pull request
events.
