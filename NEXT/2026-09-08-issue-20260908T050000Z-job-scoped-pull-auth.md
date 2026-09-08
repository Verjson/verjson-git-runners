---
date: 2026-09-08
id: 20260908T050000Z
impact: minor
refs: 198
title: Consume short-lived job-scoped Nexus pull authentication
---

Explicitly disable static job image-pull Secrets and service-account fallback,
while preserving exact image allowlists and Always pulls. Separate the manager's
bootstrap Secret from per-job OIDC credentials and record the measured GitLab
Runner 18.3.1 Secret-before-pod proof. Require canonical variable expansion,
five-minute jobs, protected-reference admission and a fresh uncached-image live
acceptance test without printing credentials or purging shared caches.

Keep the producer Go module cache in disposable writable space so the canonical
GitHub wrapper can run under the checkout owner UID rather than the image UID.
