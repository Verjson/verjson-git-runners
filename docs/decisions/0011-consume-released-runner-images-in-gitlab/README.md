# 0011 — Consume released runner images as GitLab build containers

- **Date:** 2026-09-07
- **Status:** Accepted

## Context

[Issue #198](https://github.com/Verjson/verjson-github-runner/issues/198) requires GitLab
jobs to consume this producer's released images from Nexus. The image entrypoint starts
a GitHub agent and is not a GitLab manager/helper interface. Rebuilding an incidental
consumer copy would break the existing release and provenance ownership boundary.

## Decision

Promote existing released bytes through explicit canonical dispatch, preserving immutable
source and destination digests and release evidence. Use the image solely as a Kubernetes
build container with entrypoint honoring disabled. Keep manager and helper separately
owned by GitLab, version and architecture coupled, and digest pinned in Nexus too.

Provide a credential-free configuration renderer with explicit inputs and fail-closed
structural checks. It cannot establish provenance or authenticate asserted versions;
publication and live job receipts remain mandatory. The initial profile permits one
nonroot job, finite resources, no escalation/capabilities, no host mounts or services,
and no workload service-account token. Deployment admission/network/namespace controls
must enforce these properties even against job-level configuration overrides.

## Consequences

GitHub execution and current image releases remain unchanged. No license or signature is
inferred from registry location. An approved deployment owner supplies credentials, RBAC,
manager deployment and live acceptance receipts before rollout. The source image's sudo
is blocked by the Kubernetes no-escalation context. Privileged Docker builds and arbitrary
service containers are outside this profile. Details and verification commands live in
[the consumption guide](../../gitlab/README.md).
