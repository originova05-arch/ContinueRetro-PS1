# Third-party rebuild recipes

The canonical versions/commits are `tools/locks/toolchain.lock.tsv`. Prefer `CR_FETCH_SOURCES=1 ./scripts/bootstrap.sh` to fetch exact source refs. These notes are fallbacks when a cached binary no longer runs.

- **mkpsxiso/dumpsxiso 2.30:** checkout `Lameguy64/mkpsxiso` tag `v2.30`; build the project with its CMake build files on the target OS, or use the locked official release ZIP.
- **PCSX-Redux:** checkout recursively at `2a36099dc24c5a746854e3de8359c40e5af21c10`. Linux official recipe: `./dockermake.sh appimage`; without Docker install the dependencies documented by upstream and run `make`.
- **DuckStation:** checkout `stenzek/duckstation` at `fe2306b1f0f7dd64cbc9aa8eb12269715ba799b5`; follow that revision's CMake/platform build documentation. Runtime QA should not silently update to another rolling build.
- **Ghidra:** release ZIP is the preferred reproducible executable distribution. Exact source tag is `Ghidra_12.1.3_build`; Java 21 is required by this workspace.
- **xdelta3:** prefer official `xdelta3-3.2.0-linux-x86_64.tar.gz` (SHA-256 `480295c7a41fea6503659f19ddc61676c0df4834e2292846ba97de30c68c2397`). Source fallback is tag `v3.2.0` / commit `ff322e592383227b0d65ddfde7e0e5bbc504dc15`; bootstrap builds `xdelta3/` with CMake when source/network is available.
- **jPSXdec:** Java binary ZIP is locked to v2.1 beta; source ref `v2.1` is recorded for rebuild.
