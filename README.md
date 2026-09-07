# ContinueRetro-PS1

Portable PS1 localization and reverse-engineering workspace.

## Recover after ClientError with one command

Install `ps1-thai-game-localizer v4.1` or newer, then run from the repository root:

```bash
bash ./scripts/backend_guard.sh
```

This verifies the repository, latest checkpoint, project mount, disk, pinned toolchain, and aggregate OpenAI status, then writes a durable resume packet to:

```text
WORKSPACE_META/RUNTIME_RECOVERY/RESUME_PACKET.md
```

When the pinned toolchain is missing or broken:

```bash
bash ./scripts/backend_guard.sh --fix
```

Run a long local step with before/after snapshots, sanitized logs, and a single-writer lock. Automatic retry remains off:

```bash
bash ./scripts/backend_guard.sh run -- ./games/Zoids_2/verify.sh
```

For a proven side-effect-free operation, opt in to transient retry explicitly:

```bash
bash ./scripts/backend_guard.sh run \
  --retry-transient --read-only --attempts 3 -- \
  ./games/Zoids_2/verify.sh
```

For a step that creates retained output, watch the exact output. Retry stops if that output appears or changes:

```bash
bash ./scripts/backend_guard.sh run \
  --retry-transient \
  --watch games/Zoids_2/output/result.bin \
  --attempts 3 -- \
  ./games/Zoids_2/build.sh
```

See `docs/CLIENTERROR_RECOVERY.md` for the full recovery contract.

## Manual toolchain restore

```bash
./scripts/bootstrap.sh
./scripts/doctor.sh
```

The repository stores scripts, source, configs, docs, checkpoints, and reproducibility metadata. User-owned ROM/BIN/CUE/BIOS and other private game data are intentionally excluded.
