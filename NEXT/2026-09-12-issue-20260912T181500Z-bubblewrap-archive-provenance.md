---
date: 2026-09-12
id: 20260912T181500Z
impact: patch
title: verify Bubblewrap package archive provenance at image admission
summary: The Bubblewrap image contract now uses an absolute Python interpreter, retains the exact downloaded package archive, verifies its immutable SHA-256 alongside the binary, and tests the root ownership boundary.
---

Verify the downloaded Bubblewrap package archive alongside its installed binary.
