---
date: 2026-09-17
issue: 216
title: Pin Bubblewrap per architecture instead of with one shared version
impact: patch
---

Every image build failed on its `linux/arm64` leg with
`E: Version '0.11.1-1ubuntu0.1' for 'bubblewrap' was not found`. The pin was one exact
version carried in four places — an `ARG` in `images/base.Dockerfile`, a default in each of
`scripts/install-bubblewrap.sh` and `scripts/ensure-bubblewrap.sh`, and a top-level
`version` in `images/bubblewrap-provenance.json` — and Ubuntu had stopped serving one
version to both architectures.

**One shared version was never a property the archive guarantees.** Ubuntu publishes each
architecture independently: `ports.ubuntu.com` had moved arm64 `resolute-updates` to
`0.11.1-1ubuntu0.2` while `archive.ubuntu.com` still served `0.11.1-1ubuntu0.1` to amd64 on
the same suite. Re-pinning to a different single value could not fix that, because no single
value satisfied both — so the pin model itself, not its value, is what changed.

The exact pin is kept and deliberately not loosened. `bwrap` is the sandbox boundary the
isolated runner mode depends on, so a floating version would mean the security-relevant
binary in a published image is whatever the archive happened to serve that minute, which is
not a reproducible artifact. What changes is only that "exact" is now stated per
architecture, alongside the per-architecture `package_sha256` anchors the provenance
descriptor already carried:

```json
"architectures": {
  "amd64": { "version": "0.11.1-1ubuntu0.2", "package_sha256": "8074e9e1…", … },
  "arm64": { "version": "0.11.1-1ubuntu0.2", "package_sha256": "b4b72dd8…", … }
}
```

`images/bubblewrap-provenance.json` is now the single source of that pin. Both shell
scripts resolve their own `dpkg --print-architecture` record out of it rather than carrying
a default, and `scripts/bubblewrap-image-contract.py` no longer has a
`BUBBLEWRAP_PACKAGE_VERSION` constant at all — it reads the version from the architecture
record it is already reading the checksum from. Four places that had to be edited in
lockstep became one, which is what made a partial re-pin possible in the first place.

**A detail worth recording, because it changes what this fixes.** Re-confirming the archive
while writing this showed amd64 `resolute-security` *does* serve `0.11.1-1ubuntu0.2`
(sha256 `8074e9e1…`); it is amd64 `resolute-updates` that lagged. So a single version does
currently satisfy both, and the one-line re-pin the issue ruled out would in fact have gone
green today. It was still the wrong fix: it would have depended on the security pocket
having caught up, which is the exact fragility that produced this outage, and it would have
left the next divergence — an arch-specific rebuild, a staggered pocket, a `+b1` binary
NMU — failing the same way. Both architectures are pinned to `0.11.1-1ubuntu0.2` because it
is the security update; the model no longer cares whether those two strings match.

**How the pin stays honest as the archive moves again, because it will.** Three properties
carry it, and none of them is a person remembering:

1. *It still fails closed, per architecture.* `apt-get download bubblewrap=<exact>` errors
   when the archive drops that version, so a stale record is a red build rather than a
   silently-newer binary. The blast radius of the next divergence is one architecture's
   record, and the remedy is a two-line edit instead of a model change.
2. *The installed image cannot disagree with the descriptor.* The anchor written at install
   time records the version actually fetched, and the contract rejects an image whose anchor
   version differs from its architecture's provenance record — so a build against a stale
   pin cannot publish. A record that is missing, has no `version`, or carries anything but an
   exact version string is rejected outright; there is no permissive path.
3. *Drift is detected before it reaches a release.* The pull-request leg does build both
   architectures, so architecture coverage is not what this divergence slipped through: those
   builds read the shared layer cache, which turns the download-and-checksum layer into a hit
   whenever the Dockerfile is byte-identical, so an archive move under an unchanged pin is
   never re-fetched. The weekly `image-build-check` arm64 job is cold on purpose
   (`CACHE_READ: off`) and is what closes that window, and it is now the check that catches a
   one-architecture archive move.

Verified against the real archive and real builds, not only against the unit suite: the
amd64 and arm64 base images were built from this branch, each resolving its own record,
passing the authenticated APT checksum, and passing the final in-image contract. The two new
fail-closed assertions were mutation-checked — removing the anchor-version comparison, and
removing the exact-version shape check, each fail a test that passes on restore.
