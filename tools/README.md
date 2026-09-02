# tools/

- `locks/`: exact versions, hashes, source refs and download hints.
- `cache/`: local offline archives/AppImages; Git-ignored.
- `installed/`: runnable extracted tools; Git-ignored.
- `src/`: project-owned source plus optional pinned third-party source clones.
- `bin/`: stable wrappers used by project scripts.

Nothing important should exist only in `/usr/local` or `/tmp`.
