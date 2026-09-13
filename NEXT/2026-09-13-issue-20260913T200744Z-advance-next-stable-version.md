---
date: 2026-09-13
id: 20260913T200744Z
refs: 194
title: Advance the next stable runner image version
impact: patch
---

Advance the reviewed next stable container version after `v0.2.1` so the
Bubblewrap image candidate from merged PR #196 can be promoted without
rebuilding or silently reusing a released version. Keep the release workflow
test mirror aligned with the same version.
