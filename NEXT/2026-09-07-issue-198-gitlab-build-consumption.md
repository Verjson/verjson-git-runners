---
date: 2026-09-07
issue: 198
title: Define Nexus-pinned GitLab build-container consumption
---

Add a credential-free Kubernetes runner configuration renderer for existing released
producer images promoted unchanged to Nexus. Validate immutable references and separate
GitLab manager/helper roles; constrain entrypoint behavior, nonroot execution, resource
limits and image selection. Include denial tests and document the live provenance,
credential, namespace-isolation and canary evidence still required before rollout.
