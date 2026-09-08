---
date: 2026-09-08
issue: 195
title: Reconcile standalone base inputs before release credentials
impact: patch
---

Adopt the canonical pre-credential release reconciliation contract at
`55576f7cf8659d49aa28b3fca8039b6e05d47231` and generate the candidate, release,
and changelog companions from that same immutable revision. The reviewed hook
updates only the five derived Dockerfile defaults and README base reference from
the verified release manifest. The canonical guard rejects unexpected writes and
restores the tree on failure before release credentials are minted.

Repair the standalone defaults using the attestation-verified immutable v0.2.1
base digest, without changing historical release manifests. Behavioral tests cover
all variants, idempotence, invalid manifests, missing/duplicate pins, and symlinks.
This adopts upstream ADR 0158 (Verjson/.github#1203), rather than adding a second
release authority or deriving releases from merges.
