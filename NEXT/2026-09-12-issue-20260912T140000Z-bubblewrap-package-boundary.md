---
date: 2026-09-12
id: 20260912T140000Z
refs: 194
impact: patch
title: Verify Bubblewrap package provenance at the image boundary
---

Run the final Bubblewrap image contract after all root installers and require the exact
package version, package ownership, and package checksum for `/usr/bin/bwrap` before using
its reported version. Reject writable, setuid, setgid, and sticky mode bits on the executable.
