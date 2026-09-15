---
date: 2026-09-15
issue: 208
title: Refresh canonical candidate and release contract pins
impact: patch
---

Regenerate the GitLab candidate and release adopters from the current immutable `Verjson/.github` contract `3b83ddeaa421e60005e15d36e946e2f83832bacb`, including the provenance builder identity and generated validators. This removes stale canonical contract references without claiming that an image was published or that live protected-main evidence exists; those operational gates remain tracked by #208 and CI #30.
