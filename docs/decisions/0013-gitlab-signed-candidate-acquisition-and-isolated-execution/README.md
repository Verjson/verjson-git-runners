# 0013 — GitLab signed candidate acquisition and isolated execution

- **Status:** Accepted
- **Date:** 2026-09-25
- **Issue:** [Verjson/verjson-git-runners#208](https://github.com/Verjson/verjson-git-runners/issues/208)

## Context

[Verjson/verjson-ci#30](https://github.com/Verjson/verjson-ci/issues/30) needs an
owner-delivered GitLab runner capability before live signed acquisition and native
candidate/release execution can proceed on GitLab. CI PM's coordination handoff on this
issue was resolved on 2026-09-24: verjson-git-runners accepted implementation ownership
for the GitLab signed-acquisition and candidate-isolation runtime. That handoff comment
deliberately made no code change, since this spans five distinct security-sensitive
capability areas — each touching credential handling, sandbox-escape prevention, or
production runner infrastructure — and this organization always requires an ADR before
implementing a sensitive-class change, not a single autonomous-pass patch. This ADR is
that design pass. It commits to an architecture; it does not implement one.

`Verjson/verjson-ci` already built and shipped the equivalent GitHub-side capability
(issues #85, #98, #99, #100, #102, #104, all merged), recorded as ADR 0020 (source-process
isolation), ADR 0034 (signed GitHub candidate acquisition), ADR 0031/0032 (CLI/OCI candidate
execution), ADR 0033 (protected native adapters), and ADR 0035 (approved-candidate producer
worker). Notably, ADR 0020's isolation contract is already written with GitLab Runner
18.3.1's specific behavior in mind (its Bash writer's `: | eval`, the Kubernetes executor's
variable injection, the `/scripts` volume) — it explicitly states "repository does not
change external runner implementation," meaning it already assumes some other repository
owns proving the capability exists on the actual runner fleet. This repository is that
other repository.

This repository's own investigation of installed GitLab CE 18.3.1 (issue #208 comments,
2026-09-10) found concrete bypasses a naive design would miss: developer pipeline-variable
overrides are permitted; `no_one_allowed` is the strict direct-pipeline restriction, but
`Build::Associations#apply_permissions` exempts child pipelines and on-demand DAST
validation from it; protected project/group variables can shadow predefined values.
Conditional YAML `include` guards therefore cannot alone establish pre-helper execution
identity — an authenticated, post-hoc check against GitLab's own API is required regardless
of what the pipeline YAML claims about itself.

Current live infrastructure this design must build on, not replace: `deploy/gitlab/runner.json`
already deploys a restricted-admission GitLab Runner 18.3.1 manager in Kubernetes (unprivileged
`default` job service account with no auto-mounted token, explicit egress-only `NetworkPolicy`,
namespace-scoped RBAC, `seccompProfile: RuntimeDefault`); `.verjson/runtime-candidate.json`
already pins and consumes a `Verjson/verjson-ci`-produced candidate runtime image published to
Nexus; `scripts/gitlab_build_config.py` already renders the credential-free portion of the
runner configuration. The confirmed gap is narrower than the full isolation contract: `/usr/bin/bwrap`
is absent from the GitLab Kubernetes candidate/runtime image. Issue #194 covers the shared
Bubblewrap *package* prerequisite; it does not by itself establish this GitLab image's isolation
*outcome*. Issue #214's `gha-general-*` bwrap gap is a different image and a different fleet —
same symptom shape, not the same root cause, and not fixed by fixing the other.

## Decision

Adopt `Verjson/verjson-ci`'s existing, reviewed acquisition/isolation/adapter contracts as the
architectural baseline for all five owner-outcome areas in issue #208. Do not design a parallel
GitLab-native contract from scratch. Where GitLab's job-token and pipeline model force a real
divergence from the GitHub-side design, that divergence is called out explicitly below; everything
else is adopted unchanged. Each area states what verjson-git-runners must independently own versus
what it consumes as-is.

### 1. Provenance-approved runtime + Bubblewrap packaging

Owned entirely by this repository, since it owns the runner/candidate images. Extend the existing
container-candidate promotion chain (`container_candidate_validate.py` → `container_release_manifest.py`
→ `container_attestation_verify.py`, the same chain ADR 0007 already established for the GitHub
Actions runner image) to also assert `/usr/bin/bwrap` is present, root-owned, and non-writable in
the GitLab-side candidate/runtime image referenced by `.verjson/runtime-candidate.json` and any
GitLab build/helper image. Do not fork a second promotion pipeline for this check; add the
capability assertion to the one that already exists. This is the concrete blocking prerequisite for
area 3 and should be the first sub-issue decomposed from this ADR.

### 2. Credential-free signed acquisition

Adopt unchanged from ADR 0034: a dedicated, offline, lifecycle-disabled acquisition child process
receives the transport credential only on fd3 and exits before any repository or candidate code
runs; the supervisor never reads the credential itself and closes its own fd3 copy immediately; no
credential accompanies the signed download URL; a receipt is recorded; no alternate identity is
ever synthesized on failure.

GitLab-specific divergence: the transport credential is `CI_JOB_TOKEN`, scoped to the exact
producing project through GitLab's job-token inbound allowlist — never the default open allowlist
— per ADR 0052's capability matrix, which already classifies `CI_JOB_TOKEN` as "not a general
provisioning identity" and scopes it to endpoint-limited in-pipeline reads. Acquisition must
independently re-verify, through its own authenticated GitLab API call using that job token (never
by trusting pipeline YAML predicates alone), that `pipeline.source == web`, the ref is the
protected `main`/canary branch, and the exact artifact/job IDs match what was requested — the same
check this issue's 2026-09-10 comment describes the existing "verjson-ci acquisition helper"
already performing informally. This ADR makes that check a committed contract rather than an ad
hoc helper behavior, and states explicitly why it is mandatory: the YAML-guard bypasses found in
this repository's own CE 18.3.1 investigation (child-pipeline exemption from `no_one_allowed`,
protected-variable shadowing, developer variable overrides) mean the pipeline's own declared
identity cannot be trusted without this independent, authenticated re-check. Static cross-forge
PATs, `secrets: inherit`-equivalent broad variable inheritance, and unverified pipeline-provided
variables are explicitly forbidden as substitutes for it.

### 3. Namespace/OCI isolation proof

Reused unchanged from ADR 0020; this repository's obligation is capability delivery, not contract
redesign. ADR 0020 already specifies the full isolation contract for GitLab Runner 18.3.1
specifically (separate user/PID/network/IPC/UTS namespaces via `bwrap`, fresh proc/dev/tmp, no
capabilities, no nested user namespaces, hidden `.git`/runner-scripts/sibling-jobs/acquisition-config/credential-files/host-home/Docker-socket/outer-proc,
only a private task-owned output directory writable) and states it does not itself change the
external runner implementation. This repository *is* that external runner implementation: its
decision here is to (a) deliver the capability ADR 0020 assumes exists (area 1, above), and (b)
extend `deploy/gitlab/runner.json`'s already-documented post-apply inspection checklist
(`deploy/gitlab/README.md`) to explicitly probe an admitted job pod for `/usr/bin/bwrap`,
namespace-creation rights, and the absence of every capability ADR 0020 forbids. This repository
does not re-derive or fork the isolation contract itself; a change to what isolation requires is a
change to ADR 0020, proposed upstream in `Verjson/verjson-ci`, not a local reinterpretation here.

### 4. Supervisor/candidate separation

Adopt unchanged from ADR 0033: an explicit, non-default "approved-candidate" execution profile,
activated only through a separately reviewed protected-variable override policy plus an exact
immutable caller reference — a script cannot self-authenticate an already-started job. Candidate
code never receives the workspace/checkout mount. Evidence stays unsigned CLI/OCI evidence, without
a hosted-job claim, until a separate authenticated receipt-observation step independently proves
the real hosted job graph. Missing activation excludes the candidate job entirely; there is no
degraded fallback.

GitLab-specific divergence: "activation" means a protected, environment-scoped GitLab CI/CD
variable. Reuse ADR 0058's `GitLabVariableApi` mutation boundary as-is for this write — its
construction-bound plan digest, injected `authorizationVerifier`, exclusive-lock
`mutationCoordinator` keyed by exact `(projectId, key, environmentScope)`, and
exact-`(key, environmentScope)`-match verification on every read close precisely the class of bug
this area would otherwise reintroduce (a variable write or read silently targeting the wrong
scope). Do not build a second, weaker variable-write path for this activation gate. The activation
variable must pair with a pinned, protected `.gitlab-ci.yml` job definition that a developer-supplied
pipeline variable cannot override, closing the specific bypasses this repository's own CE 18.3.1
investigation found (ordinary variable overrides, child-pipeline/on-demand-DAST exemption from
`no_one_allowed`). The runner-fleet side (the `verjson-gitlab-runner` Kubernetes deployment) must
reject any job lacking the expected protected-variable evidence rather than trusting the job's own
declared pipeline source.

### 5. Native GitLab WEB pipeline admission with rollback receipts

Adopt unchanged from ADR 0033: raw CLI/OCI evidence is not itself a hosted-job claim; a separate
authenticated receipt-observation step is required to prove the real hosted job graph.

This area is new relative to every GitHub-side ADR above it: it is the one place this design
introduces a *mutating* capability (rollback), where the GitHub-side candidate-execution work was
execution/observation-only throughout. Any rollback or activation write must go through ADR
0057/0058's trust boundary in full — construction-bound plan digest, injected authorization
verifier, exclusive-lock mutation coordinator, durable metadata-only intent/receipt journal, and
"an uncertain write requires reconciliation, must not be blindly retried." Do not build a second,
weaker mutation path for runner-fleet rollback merely because the caller is a different repository.
Concretely: a rollback receipt is a durable journal record (pipeline ID, job ID, commit SHA,
protected-variable plan digest, outcome) written through that same coordinator discipline, and
retained even on partial or uncertain failure — never silently cleaned up, matching ADR
0031/0032's "partially written evidence retained rather than overwritten" principle for the
GitHub side.

Admission repeats the `pipeline.source == web` AND protected `main`/canary ref AND exact approved
SHA check from area 2 at the admission boundary itself, rather than trusting it from acquisition
time — consistent with ADR 0020/0034's "current API protection metadata, not historical
protection evidence" principle: protection state can change between acquisition and admission, and
only a check performed at the boundary that matters is valid evidence for that boundary.

## Consequences

- This repository commits to *extending*, not reimplementing, `Verjson/verjson-ci`'s already-reviewed
  acquisition, isolation, and mutation contracts. A future change to any of ADR 0020, 0033, 0034,
  0052, 0057, or 0058 is a cross-repository dependency this repository must track and adopt, not a
  point this repository forks independently. `Verjson/verjson-ci` is an unmanaged repository from
  this PM's perspective; a defect or gap found in those upstream contracts while implementing this
  design is a report to that repository's own PM, not a local workaround here.
- No code lands in this pass. Once accepted, decompose into independently reviewable sub-issues,
  one per area: (1) image/Bubblewrap packaging and promotion-chain assertion; (2) the GitLab
  acquisition helper's committed authenticated re-check; (3) admitted-pod isolation verification
  added to the existing post-apply checklist; (4) the protected-variable activation gate; (5) the
  rollback-receipt journal. Each sub-issue still requires its own review given the sensitive-class
  classification — this ADR fixes the shape, not the review bar.
- The five areas are not independent. Area 3 cannot be verified before area 1 lands. Areas 4 and 5
  depend on the GitLab variable-mutation capability ADR 0058 delivers, which is explicitly
  project-scoped only — group-level variables, update-when-drifted reconciliation, and deletion
  remain open under `Verjson/verjson-ci#150`. This repository must not assume broader coverage than
  ADR 0058 actually ships; a sub-issue that needs group-scoped variables is blocked on that upstream
  gap, not a local design choice.
- This ADR provisions no credential, App, environment, or live infrastructure change. It is a
  decision record only, consistent with this issue's own 2026-09-24 scoping comment: "no
  implementation in this pass" and "no placeholder receipt will be used to close this issue."
- This ADR does not itself unblock `Verjson/verjson-ci#30`; it defines the shape delivery must take
  once someone picks up implementation of the decomposed sub-issues.

## References

- [ADR 0020 (verjson-ci) — Isolate signed source execution from credential processes](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0020-source-process-isolation)
- [ADR 0031 (verjson-ci) — Isolated candidate CLI execution](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0031-isolated-candidate-cli-execution)
- [ADR 0032 (verjson-ci) — Local digest-bound OCI execution](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0032-local-digest-bound-oci-execution)
- [ADR 0033 (verjson-ci) — Protected candidate native adapters](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0033-protected-candidate-native-adapters)
- [ADR 0034 (verjson-ci) — Signed GitHub candidate acquisition](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0034-signed-github-candidate-acquisition)
- [ADR 0035 (verjson-ci) — Approved-candidate producer worker](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0035-approved-candidate-producer-worker)
- [ADR 0052 (verjson-ci) — Capability-detected GitLab provisioning identities](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0052-gitlab-provisioning-capability-matrix)
- [ADR 0057 (verjson-ci) — Trusted environment mutation coordination](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0057-trusted-environment-mutation-coordination)
- [ADR 0058 (verjson-ci) — Trust boundary for GitLab CI/CD variable mutations](https://github.com/Verjson/verjson-ci/tree/main/docs/decisions/0058-gitlab-variable-mutation-trust-boundary)
- [Issue #208 (this repository)](https://github.com/Verjson/verjson-git-runners/issues/208)
- [Issue #194 (this repository) — shared Bubblewrap package prerequisite](https://github.com/Verjson/verjson-git-runners/issues/194)
- [Issue #214 (this repository) — bwrap absent on the gha-general lane](https://github.com/Verjson/verjson-git-runners/issues/214)
- `deploy/gitlab/runner.json`, `deploy/gitlab/README.md`, `.verjson/runtime-candidate.json`,
  `scripts/gitlab_build_config.py` (this repository)
