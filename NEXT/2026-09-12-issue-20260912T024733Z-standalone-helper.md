---
date: 2026-09-12
id: 20260912T024733Z
refs: 194
title: Make Bubblewrap verification available to standalone variants
impact: patch
---

Keep the fail-closed `/usr/bin/bwrap` checks active in every standalone derived image.
Each variant copies the trusted image contract helper and bootstraps the OS `bubblewrap`
package only when the attestation-verified base digest
`ghcr.io/verjson/gha-runner@sha256:3af0d4949ae7d1282be0cd7bcad0b8f0e5283dacaec014c536ca0ee2c808e7bb`,
including builds outside the same-run Bake graph, does not provide `/usr/bin/bwrap`.
Same-run builds inherit the package from the shared base and skip the fallback. The
installer is removed before the final exact exec-form contract. Regression coverage
requires one helper copy and one bootstrap before one final contract in every derived
variant.
