# 0013 — Adopt protected worker deployment with provider-specific admission

- **Date:** 2026-09-09
- **Status:** Proposed

## Context

[Issue #197](https://github.com/Verjson/verjson-git-runners/issues/197) owns
installation and live non-production deployment proof, blocking
[organization issue #629](https://github.com/Verjson/.github/issues/629).
The selected DigitalOcean host is Droplet 596126740 in the Development project
`verjson-ci` under the `verJSON Common` team. Its cloud and OS name is now
`gha-deployment-canary`, describing its deployment validation purpose. A second
peer host is provisioned in the same project and VPC, but it is not yet a
registered or admitted runner.

## Decision

Adopt the generated deployment, transport, and review-publisher artifacts from
`Verjson/.github@91c12ff5931ab7eb7c9a76276c2cadae5d780174`. Preserve the canonical
protected-default-branch credential boundary, separate provider and runner-control
authority, three independent review publishers, immutable release provenance,
canary-first sequential updates, capacity floor and append-only rollback receipts.
No consumer exception relaxes those checks.

Keep this adoption in draft until actual publisher identities, evidence and probe
adapters, fleet capacity and registration identity satisfy the contract.
`container-deployment.json` intentionally contains null trust roots and only the
currently registered runner; its canonical contract test must fail until onboarding
completes.
Do not replace nulls with fixture identities or introduce success-only adapters.
The generated broker supplies parent-owned GitHub manifest and probe transport, but
the host-export capability and controller integration remain blocked by
[organization #1281](https://github.com/Verjson/.github/issues/1281) and
[verjson-cli-cloud#504](https://github.com/Verjson/verjson-cli-cloud/issues/504);
private publisher identities alone cannot make the adopter runnable.
The intended canary group is the existing restricted `verjson-runner-canary` group;
the runner's current membership in `DigitalOcean` is an unresolved admission gap.

Preserve the historical signed repository and release-contract identities in
the selected v0.2.1 manifest. The deployment controller pin and historical release
signer pin serve different purposes and need not match. A repository rename does
not rewrite published provenance.

Future GitLab-hosted workers should reuse immutable image selection, bounded
sequential transitions, capacity checks, observation and rollback mechanics where
the GitLab runner lifecycle requires them. GitLab registration, scheduling,
credential admission and evidence remain provider-specific. A separate adopter
must prove those boundaries before activation; GitHub App checks and GitHub runner
groups cannot authorize GitLab workers. This follows ADR 0012 and organization
[ADR 0162](https://github.com/Verjson/.github/blob/e044618e2723b6f23c117643b3f2b438bdcee6e6/docs/decisions/0162-unify-portable-ci-engine-and-forge-adapters/README.md),
which supersedes ADR 0161 with a common portable CI engine and forge adapters.
It does not assume a universal fleet controller, introduce a speculative GitLab
deployment implementation or change the producer cutover.

## Consequences

The draft is a reviewable installation, not deployment authority or live acceptance
evidence. A second authorized existing non-production runner is needed to preserve
the canonical minimum of one available runner during an update. The detailed
[onboarding record](../../runner-deployment-onboarding.md) lists remaining inputs
and proof requirements. #197 stays open until those receipts are verified.
