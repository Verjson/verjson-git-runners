# 0014 — Provision the dedicated read-only host-evidence credentials on the canary host

- **Date:** 2026-09-24
- **Status:** Accepted
- **Issue:** [#197](https://github.com/Verjson/verjson-git-runners/issues/197), [Verjson/.github#1451](https://github.com/Verjson/.github/issues/1451)
- **Related:** [ADR 0013](../0013-protected-worker-deployment/README.md), [Verjson/.github ADR 0198](https://github.com/Verjson/.github/tree/main/docs/decisions/0198-confine-runner-host-evidence-credentials)
- **Category:** cloud IAM, secrets handling (sensitive class)

## Context

`Verjson/.github#1451`, `#1281`, and `#197` formed a closed dependency cycle: `#197`
was blocked on `#1281`, `#1281` on `#1451`, and `#1451` on `#197`'s Pulumi-managed
environment policy and dedicated read-only SSH credential. `.github` ADR 0198 already
specified the exact shape required — four secrets scoped only to the `production`
GitHub environment (`RUNNER_HOST_EVIDENCE_APP_PRIVATE_KEY`,
`RUNNER_HOST_EVIDENCE_SSH_PRIVATE_KEY`, `RUNNER_HOST_EVIDENCE_DOCTL_CONFIG`,
`RUNNER_HOST_EVIDENCE_KNOWN_HOSTS`) — but no operator had provisioned them, and the
already-merged controller code (`Verjson/.github` PR #1525/#1529/#1531) had never
been exercised against a live host.

Breaking the cycle required provisioning real credentials against `gha-deployment-canary`
(Droplet 596126740, DigitalOcean project `verjson-ci`), the non-production canary host
ADR 0013 already designated. `gha-deployment-peer` (Droplet 599398725) was initially
considered but is a bare, unadmitted host with no runner deployed — `gha-deployment-canary`
already carries a real, passed admission (GitHub runner `gha-general-10`, agent id 512).

## Decision

1. **GitHub App.** A dedicated App (`runner-host-evidence`, App ID 5062258) was created
   with exactly `metadata:read`, `contents:read`, `attestations:read`,
   `organization_self_hosted_runners:read` — no broader scope — and installed at the
   organization level (required, since `organization_self_hosted_runners` is an
   org-scoped permission) with repository selection limited to
   `Verjson/verjson-git-runners`. Its private key was set directly by the repository
   owner into the `RUNNER_HOST_EVIDENCE_APP_PRIVATE_KEY` environment secret; it was
   never transmitted through chat, an issue, or any durable record this session
   controls.
2. **DigitalOcean credential.** A new DigitalOcean API token, scoped read-only, was
   created by the repository owner (not derivable from any existing broader-privilege
   `doctl` session) and set directly as `RUNNER_HOST_EVIDENCE_DOCTL_CONFIG` (a
   `doctl` `config.yaml` containing only `access-token:`), for the same reason: a
   CI-embedded automated credential must never share a blast radius with an
   interactive human credential.
3. **Dedicated read-only SSH key, with a real enforcement mechanism.** A new
   ed25519 keypair was generated for this purpose alone. Its public half is installed
   in `gha-deployment-canary`'s `authorized_keys` restricted to
   `command="/usr/local/sbin/verjson-runner-host-evidence-gate",no-pty,no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-user-rc`.
   A bare `command="bash -s"` restriction would not have been a restriction at all:
   sshd only overrides the client's requested argv, not its stdin, and
   `@verjson/cli-cloud`'s transport invokes exactly `ssh ... "bash -s"` with the
   evidence script piped via stdin — so an unrestricted `bash -s` forced-command
   would still execute anything sent to it.

   The installed gate (`verjson-runner-host-evidence-gate`, root:root, mode 0700) is
   an allowlist, not a denylist: it accepts the two permitted parameter lines
   (`runner_id=<positive integer>`, `runner_name='<shell-quoted value>'`) and requires
   every remaining line to match, byte-for-byte by SHA-256
   (`9e6a95ac3a71a2255873fce71b4b090f241c53ba632f0b7631163eab5fdf04f1`), the exact
   static body `@verjson/cli-cloud@1.0.0`'s `runnerHostEvidenceInput()` emits — computed
   by executing the real shipped function, not transcribed from source, to eliminate
   transcription risk in a security control. Any other input, including a valid-looking
   script with one byte changed, is rejected before anything executes. Verified: a
   legitimate request for a different runner id/name passes; an injected command
   appended to an otherwise-real script is rejected and never runs; an arbitrary
   command sent directly (ignoring the generated script) is rejected; the credential
   cannot open an interactive shell.
4. **Known-hosts.** The real SSH host key fingerprints for `134.209.171.181` (both
   `ssh-rsa` and `ssh-ed25519`) were captured directly over an already-authenticated
   connection to the droplet, verified as belonging to `gha-deployment-canary`, and
   set as `RUNNER_HOST_EVIDENCE_KNOWN_HOSTS`.
5. **`container-deployment.json` correction.** `expectedRelease.sourceRepository` was
   `Verjson/verjson-github-runner` (the repository's pre-rename name, which GitHub
   still redirects but which a signer-identity check should never depend on). Corrected
   to the canonical `Verjson/verjson-git-runners`.

## Consequences

- Exercising the corrected pipeline end-to-end (diagnostic patch, not deployed) against
  `gha-deployment-canary` produced real, valid host evidence — proving every provisioned
  credential and the gate script work correctly. Two upstream defects in
  `@verjson/cli-cloud@1.0.0`'s `runnerHostEvidenceInput()` were found in the process and
  reported, not patched here (`Verjson/verjson-cli-cloud#536`): a `df -Pi --output=`
  flag conflict on current GNU coreutils, and a `pipefail`-plus-`for`-loop bug that
  silently kills the whole script whenever any of `docker`/`jq`/`pwsh` is absent from the
  host (true of most hosts). **Real, CI-driven host evidence will not succeed until
  `verjson-cli-cloud` ships a fix and the pinned dependency is bumped** — this ADR
  provisions the credential path, not a working end-to-end automated run.
- The App installation, SSH credential, and DO token are confined to
  `Verjson/verjson-git-runners`'s `production` environment only, per `.github` ADR 0198;
  none were copied to organization or repository-level secrets.
- The forced-command gate is pinned to today's exact shipped script body. If
  `verjson-cli-cloud` changes `runnerHostEvidenceInput()`'s static body for any reason
  (including fixing the two bugs above), the gate's pinned SHA-256 must be updated in the
  same change, or the legitimate evidence request will itself be rejected. This is a
  deliberate fail-closed property, not a defect: a silently-updated gate would defeat the
  point of pinning it.
- `gha-deployment-canary` is non-production per `#197`'s explicit scope; no production
  DigitalOcean resource, GitHub environment, or credential was touched.
