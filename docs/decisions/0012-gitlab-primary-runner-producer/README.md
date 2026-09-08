# 0012 — Make GitLab the primary runner producer

- **Date:** 2026-09-08
- **Status:** Accepted

## Context

[Issue #201](https://github.com/Verjson/verjson-github-runner/issues/201) records
the requested rename to `verjson-git-runners`, GitLab migration, and canonical
`verjson-ci` publication to Nexus. ADR 0011 separates build images from GitLab
manager/helper images.

## Decision

Use `https://git.159-195-78-163.nip.io/Verjson/verjson-git-runners` as the primary
source repository and `Verjson/verjson-git-runners` as the GitHub identity.
Keep the `gha` binary, `GHA_DIR`/`GHA_REF` overrides, existing checkout directory,
and GitHub runner entrypoint compatible. The Go module follows the primary
source identity. New installer clones use GitLab; existing clones retain their
configured origin until their owner explicitly migrates them.

Consume an immutable shared `verjson-ci` GitLab pipeline, with explicit release
dispatch and Nexus destination approval. Merges do not publish stable versions.
Publication must retain verified image digests, signatures, provenance and SPDX
evidence, using short-lived OIDC credentials. GitLab manager/helper images remain
separate, version-coupled upstream artifacts.

Historical `RELEASES/` manifests, changelogs, ADRs, attestations and source image
identities are immutable. Renaming a repository cannot rewrite signed evidence
or grant rights to its contents. The GHCR retention observer accepts only the new
workflow repository identity; pre-rename observations cannot extend its deletion
observation window. It remains read-only.

## Consequences

GitHub automation remains enabled until a live GitLab canary proves testing,
Nexus pull/publication, credential denial and recovery. Generated GitHub callers
stay pinned to their canonical contract and are regenerated for identity changes.
The repository rename/import and pipeline bootstrap need separate operational
receipts; this source change alone is not evidence of a completed cutover.
Archival and mirroring policy remain an explicit cutover decision.
