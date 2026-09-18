---
date: 2026-09-12
id: 91c12ff
impact: patch
title: Repin protected deployment to canonical transport
---

For runner issue #197, regenerate the protected deployment and review artifacts
from the immutable `Verjson/.github` broker contract
`91c12ff5931ab7eb7c9a76276c2cadae5d780174`, including its credential-separated
manifest and canary transport. Preserve null publisher trust roots and absent
consumer evidence/probe adapters while the canonical readiness gate remains
fail-closed. Record the provisioned peer as cloud capacity only; it is not runner
admission or live deployment evidence.
