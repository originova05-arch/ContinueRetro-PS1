# ContinueRetro-PS1 operating rules

These rules apply to every fresh chat, machine, and runtime working on this repository.

## 1. Read-first gate

Before changing any game data, read:

1. `AGENTS.md`
2. `README.md`
3. `TOOLCHAIN.md`
4. the target game's `CHECKPOINT_LATEST.md` and the checkpoint it references

If a checkpoint pointer is broken or missing, stop game modification and reconstruct the last confirmed state from tracked hashes, README/reference/runtime/rollback records. Record the repair in a new checkpoint.

## 2. Portable/offline toolchain gate

A fresh runtime must restore the project toolchain before game work.

Preferred order:

1. Restore the latest compatible GitHub Actions recovery artifact into the repository-local `tools/installed/` tree.
2. Restore user project assets such as FontKit into `tools/cache/` when required.
3. Run:

```bash
./scripts/bootstrap.sh
./scripts/doctor.sh --toolchain-only
```

Do not modify game resources until the doctor prints:

```text
READY: PS1 localization toolchain healthy.
```

Required core tools include CMake, Ninja, mkpsxiso, dumpsxiso, xdelta3, Ghidra, jPSXdec, DuckStation, PCSX-Redux, ContinueRetro PS1 utilities, and the PS1/MIPS compiler wrappers.

Project tools must be restored beneath the repository. Do not rely on `/tmp`, `/usr/local`, or leftover directories from another runtime as project state.

## 3. Private-data boundary

Never commit or push:

- ROM/disc images
- BIOS files
- original or rebuilt BIN/CUE images
- `PRIVATE/`
- ordinary `tools/cache/` or `tools/installed/` binary caches

Only push project-owned scripts/source/config/docs/checkpoints/hashes and other reproducibility metadata that contain no private game bytes.

## 4. Zoids 2 workflow

Use the reproducible sequence under `games/Zoids_2/`:

```bash
./extract.sh
./patch.sh
./build.sh
./verify.sh
```

Never modify the canonical base image in place. Work and outputs belong under Git-ignored private/work directories.

## 5. Milestone checkpoint requirements

For every retained milestone record at least:

- parent/base SHA-256
- output SHA-256 when a build exists
- files changed
- LBA/raw-sector allowlist or explicit `none`
- runtime QA environment and PASS/FAIL/PENDING result
- rollback target
- decisions and failed experiments that affect the next attempt
- next action

Update the target game's `CHECKPOINT_LATEST.md` to point to the retained checkpoint.
