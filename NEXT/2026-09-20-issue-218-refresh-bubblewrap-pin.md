---
date: 2026-09-20
issue: 218
impact: patch
title: Refresh Bubblewrap package pin
---

Refresh the exact per-architecture Bubblewrap package pin and its expected version
map to Ubuntu's current Resolute `0.11.1-1ubuntu0.3` package. Keep behavioral test
fixtures independent from the production pin. Image builds no longer request the
expired `0.11.1-1ubuntu0.2` version.
