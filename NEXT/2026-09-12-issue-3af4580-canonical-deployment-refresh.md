---
date: 2026-09-12
id: 3af4580
impact: patch
title: Repin protected deployment to bounded canonical transport
---

Regenerate the protected deployment and review artifacts from the immutable
`Verjson/.github` contract `3af4580b7d345602891fea91c2684b3bb7892c36`. The
generated controller validates complete runner admission before mutation, and
the transport sanitizes SSH-agent state and bounds replay inventory requests.
Review trust roots, host-export adapters, and second-runner capacity remain
explicit fail-closed inputs.
