---
date: 2026-09-12
id: 20260912T234500Z
impact: patch
title: bind Bubblewrap archives to immutable image provenance
summary: published image provenance now carries the architecture-specific signed APT archive digest, and the final image contract rejects an anchor or archive that does not match that immutable record.
---

Bind the verified Bubblewrap package archive to immutable per-architecture image provenance.
