---
date: 2026-09-08
issue: 201
title: Prepare the renamed GitLab primary runner producer
---

Point new installer clones and the Go module at verjson-git-runners on GitLab,
retain existing gha launcher compatibility, and start renamed GHCR observation
history without rewriting historical signed releases. Document the staged
canonical CI and Nexus publication cutover in ADR 0012.

Handle detached installer sessions without a controlling terminal by using the
existing no-launch path rather than aborting on an unreadable TTY device.
