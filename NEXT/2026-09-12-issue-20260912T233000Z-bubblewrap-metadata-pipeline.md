---
date: 2026-09-12
id: 20260912T233000Z
impact: patch
issue: 194
title: keep signed Bubblewrap metadata extraction pipe safe
summary: the Bubblewrap installer now consumes the complete apt metadata stream before selecting its first SHA256 field, avoiding a pipefail false failure during standalone image builds.
---

Keep authenticated package metadata extraction compatible with strict pipefail image builds.
