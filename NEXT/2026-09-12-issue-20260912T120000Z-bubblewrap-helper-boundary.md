---
date: 2026-09-12
id: 20260912T120000Z
refs: 194
impact: patch
title: Bound Bubblewrap installation and helper trust
---

Pin the Ubuntu Bubblewrap package to `0.11.1-1ubuntu0.1` for both the shared base and
standalone fallback. Copy the final image contract helper after all image construction so
no later mutating `COPY` or `RUN` can replace the pathname executed by the final contract.

The runtime contract treats `/usr/bin/bwrap --version` as compatibility evidence only; it
does not claim package provenance from self-reported output. This preserves the fail-closed
descriptor and ancestry checks while keeping #194 as the prerequisite for #208.
