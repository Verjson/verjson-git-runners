---
date: 2026-09-24
issue: 197
title: Provision dedicated read-only host-evidence credentials on the canary host
---
Provisioned the four `production`-environment secrets `.github` ADR 0198 requires
(`RUNNER_HOST_EVIDENCE_APP_PRIVATE_KEY`, `RUNNER_HOST_EVIDENCE_SSH_PRIVATE_KEY`,
`RUNNER_HOST_EVIDENCE_DOCTL_CONFIG`, `RUNNER_HOST_EVIDENCE_KNOWN_HOSTS`) against
`gha-deployment-canary`, and corrected `container-deployment.json`'s
`expectedRelease.sourceRepository` from the pre-rename `verjson-github-runner` to the
canonical `verjson-git-runners`. Breaks the `#197` / `Verjson/.github#1281` /
`Verjson/.github#1451` dependency cycle. See ADR 0014 for the credential design and
`Verjson/verjson-cli-cloud#536` for two upstream bugs found while exercising it live.
