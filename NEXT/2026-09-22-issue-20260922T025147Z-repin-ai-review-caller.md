---
date: 2026-09-22
id: 20260922T025147Z
impact: patch
title: Repin the AI review caller to the canonical check migration
---
Regenerated .github/workflows/ai-review-merge.yml from canonical Verjson/.github commit e3a3696fee8055b35d485bb3132055cfdb12cf45. Updated the caller verifier to track this immutable pin separately while retaining the declared pins for the other AI callers. Verified checks: write is limited to this generated caller, authorization inputs are forwarded, and no legacy-owner acceptance appears in the caller. Part of Verjson/.github#1540.
