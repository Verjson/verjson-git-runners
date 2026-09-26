---
date: 2026-09-26
issue: 223
impact: minor
title: Implement the runner-deployment evidence and probe adapters
---

`container-deployment.json` named `scripts/runner-deployment-evidence.py` and
`scripts/runner-deployment-probe.py` as `evidenceCommand`/`probeCommand`, but
neither existed — the last remaining failure in
`scripts/container-deployment-contract.test.sh` after #197's App-wiring work.

Both adapters run in the deployment controller's stripped subprocess sandbox
(`PATH`, `LANG`, `LC_ALL`, `TMPDIR`, `SSL_CERT_FILE`, `SSL_CERT_DIR` only — no
`GH_TOKEN`, App JWT, or SSH credential). `runner-deployment-evidence.py`
resolves the requested manifest identity against this repository's own
`RELEASES/containers/*.json` history, then independently confirms it against
the real GitHub release asset via unauthenticated public API calls (verified:
release/asset metadata and asset content are unauthenticated-readable for a
public repository; the self-hosted-runners and Actions-artifact-download APIs
are not). The controller's own privileged host-export transport re-verifies
the proposed manifest and its attestation before trusting it, so this adapter
only needs to propose correct values, not cryptographically prove them itself.

`runner-deployment-probe.py` is a structural sanity check on its own input,
not an independent functional canary: by the time it runs, the controller has
already independently verified the update via its privileged host-export
transport, and this sandbox has no credential to check anything further
itself.

`--rollback-receipt` is explicitly not implemented: retained deployment
receipts exist only as 90-day GitHub Actions artifacts, and downloading one
requires authentication this sandboxed adapter does not have. Documented as a
known limitation with a clear, fail-closed error rather than fabricated
output.
