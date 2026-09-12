---
date: 2026-09-12
id: 20260912T223000Z
impact: patch
title: preserve verified Bubblewrap bootstrap for standalone images
summary: Derived runner images now carry the pre-install verification helper so they can recover from older base images without installing an unanchored Bubblewrap package.
---

Keep standalone language images on the authenticated Bubblewrap acquisition path when their base image predates the package anchor.
