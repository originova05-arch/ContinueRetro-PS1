# ContinueRetro-PS1 operating rules

These rules apply to every fresh chat, machine, and runtime working on this repository.

## 1. Read-first gate

Before changing any game data, read:

1. `AGENTS.md`
2. `README.md`
3. `TOOLCHAIN.md`
4. the target game's `CHECKPOINT_LATEST.md` and the checkpoint it references
5. `WORKSPACE_META/RUNTIME_RECOVERY/RESUME_PACKET.md` when present

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
- browser HAR files, cookies, tokens, secrets, or raw ClientError diagnostics containing headers

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

## 6. ClientError and interrupted-session resilience

Authoritative state must never exist only in chat history. Before a long or externally dependent action, and after every retained result, persist state to project/repository files using atomic writes.

Use the backend guard:

```bash
bash ./scripts/backend_guard.sh
```

For a local command that may take time or produce retained artifacts, prefer:

```bash
bash ./scripts/backend_guard.sh run -- <command> [args...]
```

The guard creates before/after snapshots, a sanitized journal, a resume packet, and a metadata-only recovery bundle. Retry is disabled by default. Enable it only for a proven read-only command or while fingerprinting every retained output; deterministic failures are never retried automatically.

After `ClientError`, timeout, lost WebSocket, runtime restart, or uncertain completion:

1. do not immediately repeat an action that may have written files;
2. run `bash ./scripts/backend_guard.sh`;
3. inspect existing output paths and hashes against the resume packet and latest checkpoint;
4. classify the interrupted action as completed, failed, or unknown;
5. execute only one safe next transition and checkpoint it.

Do not reset, clean, overwrite, or regenerate authoritative files merely to make the runtime appear consistent. Preserve unknown outputs until their provenance is resolved.

## 7. Concurrency and retry policy

Only one guarded retained-write command may run per repository/runtime state directory. A live lock blocks a second guarded command regardless of age. A different-host lock on shared storage remains blocking until its stale window expires.

Automatic retry is opt-in and limited to transient classes such as ClientError, timeout, connection reset, HTTP 429, and HTTP 5xx. It requires either `--read-only` or at least one `--watch PATH`. Any watched output creation/change blocks retry with `WATCHED_OUTPUT_CHANGED_REVIEW_REQUIRED` and requires provenance review.

Syntax errors, failed assertions, hash mismatches, missing files, invalid pointers, wrong inputs, and failed QA gates are deterministic failures and must not be retried unchanged.
