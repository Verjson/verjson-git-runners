---
date: 2026-09-09
id: 20260909T165530Z
impact: patch
title: Adopt exact attested manifest bytes for deployment
---

Regenerate all ten deployment artifacts at the repaired immutable organization
contract. Preserve attested release-asset bytes for admission and baseline
reconciliation instead of reserializing signed JSON. Document the remaining
canonical adapter transport blocker, missing publisher identities and fleet
onboarding inputs; the unchanged deployment readiness gate remains fail-closed.
