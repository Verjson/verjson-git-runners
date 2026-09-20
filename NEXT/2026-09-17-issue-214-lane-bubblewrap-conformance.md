---
date: 2026-09-17
issue: 214
impact: patch
title: Probe the delivered lane for the Bubblewrap image contract
---

Assert the Bubblewrap image contract against the runner the shared lane actually delivers,
not only against the image this repository builds. `images/base.Dockerfile` has refused to
publish an image without a root-owned `/usr/bin/bwrap` since #194, but nothing observed the
image the fleet was running: the newest release manifest remained `v0.2.1` from 2026-08-27,
whose `gha-runner-pwsh` amd64 digest
`sha256:4eefaa4e634366c1f22dfae1f19196ff82a5bf5bb5733ccb9433273939689af3` contains no
`bwrap` at all, so `Verjson/verjson-cli` met the gap as a red `main` on `gha-general-9`
rather than as a red check here.

This change adds detection only; releasing the fixed image and repointing the target
fleet manifest remain outstanding work under #214.

The new scheduled `lane conformance` workflow runs the same
`scripts/bubblewrap-image-contract.py` the image build runs, on the lane, through the
organization lane variable and with no hosted fallback — a probe that silently reroutes to
a GitHub-hosted runner would report an unrelated runner's conformance as this lane's.
It is deliberately not a pull request check, because no diff here can change what the
deployed fleet runs. It has no manual dispatch trigger that could select contributor-branch
code for execution on the self-hosted lane; the scheduled job is main-only and explicitly
checks out `main`.
