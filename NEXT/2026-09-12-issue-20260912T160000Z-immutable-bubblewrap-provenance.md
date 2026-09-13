---
date: 2026-09-12
id: 20260912T160000Z
refs: 194
impact: patch
title: Anchor Bubblewrap checks to immutable package provenance
---

Verify the final `/usr/bin/bwrap` against architecture-specific SHA-256 values recorded
from the exact pinned Ubuntu package artifact. Copy that provenance after image mutation
and before the final contract helper, so rewritten dpkg metadata cannot authorize a
replacement binary.
