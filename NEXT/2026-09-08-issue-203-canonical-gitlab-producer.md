---
date: 2026-09-08
issue: 203
impact: minor
title: Adopt canonical GitLab producer verification and Nexus promotion
---

Run producer source and security checks through the immutable verjson-ci GitLab
interface using Nexus-pinned images. Bind successful checkout tests, the original
signed release manifest and explicit SBOM-reference evidence to a dispatch plan
for all six Nexus runner variants. Preserve old signed source identities while
using the renamed Nexus destination. Publication remains an explicit protected
manual operation with broker-approved short-lived OIDC credentials.

Permit one exact Nexus canonical CI bootstrap candidate in the runner image
allowlist, explicitly recording its reviewed commit and license inventory digest
without claiming a signed stable release.

Persist the reviewed secret-free Kubernetes canary manifest. Use the GitLab 18.3.1
advanced PodSpec patch for RuntimeDefault seccomp, explicit unprivileged job
service account, disabled label overrides and writable nonroot script/log paths
without relaxing restricted namespace admission.
