---
date: 2026-09-12
id: 20260912T232000Z
impact: patch
issue: 194
title: repair standalone Bubblewrap fallback installation
summary: derived runner images now pass the pinned Bubblewrap version through env when the shared ensure helper invokes the authenticated installer, and the PowerShell image includes the same fallback assets.
---

Make standalone derived runner image builds recover the verified Bubblewrap package without exposing mutable package metadata.
