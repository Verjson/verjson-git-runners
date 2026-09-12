---
date: 2026-09-12
id: 20260912T210000Z
impact: patch
title: anchor Bubblewrap packages to authenticated APT metadata
summary: Bubblewrap images now verify package bytes against the authenticated APT SHA-256 before installation, record that anchor in the image, and derive the installed binary check from the verified package archive.
---

Prevent a mutable image provenance descriptor from approving a self-consistent package and binary replacement during runner image construction.
