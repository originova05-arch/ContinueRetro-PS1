# PS1 Localization Toolchain

Toolchain lock date: **2026-09-02 (Asia/Bangkok)**. Exact machine-readable refs are in `tools/locks/toolchain.lock.tsv`.

| Program | Version/ref | Role | Portable path | Install/build | Dependencies | OS/architecture |
|---|---|---|---|---|---|---|
| Ghidra | 12.1.3 / `Ghidra_12.1.3_build` | MIPS/PS-X EXE reverse engineering; renderer/font/string analysis | `tools/installed/ghidra/ghidra_12.1.3_PUBLIC/` | `bootstrap.sh` extracts locked ZIP; exact source tag recorded | Java 21 | Java platforms; headless tested Linux x86_64 |
| mkpsxiso | 2.30 | PS1 image rebuild, fixed LBA layout, LBA logs | `tools/installed/mkpsxiso/.../bin/mkpsxiso` | Locked Linux/Darwin ZIP; source tag `v2.30` | release-native libs | Linux x86_64 tested; Darwin package cached |
| dumpsxiso | 2.30 | BIN/CUE extraction and XML/LBA generation | same package as mkpsxiso | same | same | Linux x86_64 tested |
| jPSXdec | 2.1 beta | STR/XA/media/CD-sector inspection | `tools/installed/jpsxdec/jpsxdec_v2.1-beta/` | locked ZIP | Java | tested Java 21 |
| DuckStation | 0.1-11826-gfe2306b1f; commit `fe2306b1f0f7...` | Runtime QA/screenshots/controller validation | `tools/installed/duckstation/` | exact AppImage cache preferred; exact source commit recorded | Linux display/Xvfb; software renderer recommended in this container | Linux x86_64 tested |
| PCSX-Redux | commit `2a36099dc24c...` | Debugger/runtime/reverse engineering | `tools/installed/pcsx-redux/` | exact AppImage cache; exact source commit recorded | bundled native dependencies | Linux x86_64 tested |
| xdelta3 | 3.2.0 / tag `v3.2.0` | User-distributable delta patch creation/application | `tools/installed/xdelta3/xdelta3` | locked Linux x86_64 tarball from `tools/cache/`; otherwise exact release download or pinned CMake source build | no runtime dependency for locked binary; CMake + C/C++ compiler for source build | Linux x86_64 release installed/tested; source ref also pinned for rebuild |
| FFmpeg | 7.1.5 (runtime-tested) | Media inspection/transcode; XA/STR QA support; screenshot/video pipelines | system package; checked by `bootstrap.sh`/`doctor.sh` | Debian/Arch/Homebrew package install via `scripts/install_system_deps.sh` | codec libraries bundled by OS package | Linux x86_64 tested; macOS package recipe included |
| ImageMagick | 7.1.2-1 (runtime-tested) | Bitmap/font atlas inspection, crop/montage/GIF/image QA | system package; checked by `bootstrap.sh`/`doctor.sh` | Debian/Arch/Homebrew package install via `scripts/install_system_deps.sh` | OS image libraries | Linux x86_64 tested; macOS package recipe included |
| PS1 MIPS Clang/LLD wrappers | Clang/LLD 17 tested; MIPS-I target | Compile/link renderer hooks and small PS1 payloads for R3000A/MIPS-I | `tools/bin/ps1-mips-*`; smoke test in `tools/tests/` | bootstrap installs host Clang/LLD/LLVM tools when absent | clang, ld.lld, llvm-objcopy, llvm-objdump | Linux x86_64 tested; package recipes for macOS/Linux |
| Continue Retro Thai Game FontKit | 1.2.1 | Thai glyph sources/profiles/placement/QA scripts | `tools/installed/fontkit/`; rebuild source/config under `tools/src/fontkit/` | user project asset + Python builders | Python requirements in kit | cross-platform Python; Zoids 2 target 16×13 |
| ContinueRetro PS1 utils | repo version | Shift-JIS scan, raw 2352 helper, LBA map, PS-X EXE header inspection | `tools/src/continue-retro-ps1-utils/` | source tracked in repo | Python 3 | cross-platform Python; shell wrappers Unix-like |

## Use

```bash
export PATH="$PWD/tools/bin:$PATH"
mkpsxiso --help
dumpsxiso --help
jpsxdec -help
ghidra-headless ...
duckstation ...
pcsx-redux ...
```

## Rebuildability

`tools/cache/` and `tools/installed/` are a local offline convenience cache and are Git-ignored because several binaries are large. Their SHA-256 values and exact source refs are tracked. On a networked machine, cache the exact third-party source trees as well:

```bash
CR_FETCH_SOURCES=1 ./scripts/bootstrap.sh
```

If a binary no longer works on a new OS/architecture, rebuild the recorded source ref rather than silently upgrading.

## Runtime QA reference for Zoids 2

- BIOS: user-owned `SCPH5500.BIN` (private), SHA-256 `9c0421858e217805f4abe18698afea8d5aa36ff0727eb8484944e00eb5e7eadb`.
- DuckStation: software renderer in the container/Xvfb environment.
- Controller: if navigation is inactive, use DuckStation quick-menu **Toggle Analog** before testing input.

Game images/BIOS are deliberately kept under `PRIVATE/` and excluded from Git.

## Media command reference

The user-supplied FFmpeg/ImageMagick command notes are preserved unchanged at `docs/reference/ffmpeg-imagemagick.md`. They are a command reference, not installer binaries.

## PS1 MIPS compiler smoke test

```bash
./scripts/verify_mips_toolchain.sh
```

The wrappers target little-endian MIPS-I (`mipsel-none-elf`, `-march=mips1`, ABI32, soft-float), appropriate for PS1 R3000A hook/payload work. GCC `mipsel-none-elf` remains optional for projects that specifically require the GNU toolchain.
