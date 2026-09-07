# ClientError and interrupted-session recovery

A `ClientError`, lost WebSocket, timeout, browser crash, Codex disconnect, or runtime restart is an execution interruption. It is not evidence by itself that the game database, BIN/CUE, or last build is corrupt.

This repository uses the recovery layer included in `ps1-thai-game-localizer v4.1` or newer. The authoritative state remains the repository, project files, hashes, latest checkpoint, and exact build manifests—not the last chat message.

## One-command recovery

From the repository root:

```bash
bash ./scripts/backend_guard.sh
```

This resolves the installed `retrothai` launcher, verifies the repository and checkpoint, checks the project mount, disk, pinned toolchain, and aggregate OpenAI status, then writes sanitized recovery metadata under:

```text
WORKSPACE_META/RUNTIME_RECOVERY/
├── LATEST_SNAPSHOT.json
├── RESUME_PACKET.md
├── ERROR_EVENTS.jsonl
├── JOURNAL.jsonl
├── runs/
├── snapshots/
└── bundles/
```

The recovery bundle is metadata-only. It excludes ROM/BIN/CUE/BIOS, full rebuilt images, extracted copyrighted assets, browser HAR files, cookies, API keys, tokens, and other private game bytes.

Use `--fix` only when the report says the pinned toolchain is not ready:

```bash
bash ./scripts/backend_guard.sh --fix
```

When the authoritative project is outside the repository, pass it explicitly once or register it through `retrothai`:

```bash
bash ./scripts/backend_guard.sh --project "/Volumes/SSD/RetroThai/PRIVATE/PROJECTS/Zoids_2"
```

## Guard a local command

Snapshots, logs, and single-writer locking are enabled without automatic retry:

```bash
bash ./scripts/backend_guard.sh run -- ./games/Zoids_2/verify.sh
```

Transient retry is disabled by default. Opt in only with one of these safety contracts.

For a genuinely side-effect-free command:

```bash
bash ./scripts/backend_guard.sh run \
  --retry-transient --read-only --attempts 3 -- \
  ./games/Zoids_2/verify.sh
```

For a command that creates retained output, watch every relevant output path:

```bash
bash ./scripts/backend_guard.sh run \
  --retry-transient \
  --watch games/Zoids_2/output/result.bin \
  --attempts 3 -- \
  ./games/Zoids_2/build.sh
```

The guard fingerprints watched outputs before and after every attempt. If an output appears or changes after a failed attempt, retry stops with `WATCHED_OUTPUT_CHANGED_REVIEW_REQUIRED`; the existing output must be checked against its expected hash and provenance before any rerun.

Deterministic failures—hash mismatch, failed assertion, missing file, invalid pointer, syntax error, failed QA gate, or wrong input—are never retried automatically.

## After ClientError

1. Do not immediately repeat an action that may have written files.
2. Run `bash ./scripts/backend_guard.sh`.
3. Open `WORKSPACE_META/RUNTIME_RECOVERY/RESUME_PACKET.md`.
4. Verify existing outputs and hashes against the latest checkpoint and build manifest.
5. Classify the interrupted action as `COMPLETED`, `FAILED`, or `UNKNOWN`.
6. Preserve unknown output until its provenance is resolved.
7. Execute only one safe next transition and checkpoint it.

## Record an incident

```bash
bash ./scripts/backend_guard.sh record-error \
  "ClientError while creating response" --surface ChatGPT
```

Messages and nested command arguments are redacted before persistence. Never commit HAR files or raw diagnostics containing authorization headers, cookies, query tokens, or private URLs.

## Browser/client-side checks

The repository guard cannot repair OpenAI infrastructure, a browser extension, VPN, proxy, secure DNS, or a failing local network. For repeated client errors, check OpenAI Status, use a fresh chat when the conversation is very long, restart the app/browser, test a private window with extensions disabled, temporarily disable VPN/proxy/secure DNS, and try another network. Keep any HAR evidence private.
