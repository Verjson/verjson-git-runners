---
date: 2026-09-12
id: 20260912T193000Z
impact: patch
title: close Bubblewrap verification race windows
summary: Bubblewrap image admission now reopens and revalidates the package archive after execution, opens protected files without FIFO blocking, and pins shipped package and binary checksums in tests.
---

Close archive replacement and special-file race windows in the Bubblewrap image contract while preserving fail-closed provenance checks.
