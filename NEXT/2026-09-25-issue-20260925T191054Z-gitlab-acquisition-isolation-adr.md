---
date: 2026-09-25
id: 20260925T191054Z
refs: 208
title: Record the GitLab signed candidate acquisition and isolation design
---

Adds ADR 0013, the design pass this issue's 2026-09-24 ownership-acceptance comment
deferred: how verjson-git-runners extends Verjson/verjson-ci's already-reviewed
candidate acquisition, isolation, and variable-mutation contracts (ADRs 0020, 0031-0035,
0052, 0057-0058) across the five owner-outcome areas issue #208 names, with the concrete
GitLab CE 18.3.1 bypasses this repository's own investigation found. No implementation
code changes in this pass; the ADR fixes the architecture sub-issues must follow once
delivery is picked up.

A separate fragment for the same issue is needed rather than extending the existing
2026-09-15 one: `NEXT/`'s own convention forbids editing another entry's file, and this
fragment uses `id:`/`refs:` instead of `issue:` to avoid colliding with that entry's
already-owned `issue:208` identity.
