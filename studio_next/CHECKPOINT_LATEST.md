# CHECKPOINT — London-first / Quality Core / Source Recovery

Updated: 2026-09-08 (Thailand)

## Status

- Repository: originova05-arch/ContinueRetro-PS1
- Work branch: studio/london-quality-checkpoint-20260908
- Main branch: not modified by this work
- User app baseline: ContinueRetro Studio v0.6.0
- Quality core + review input boundary: ISOLATED_UNIT_TESTED / NOT_INTEGRATED
- Latest retained addition: SOURCE_RECOVERY_HELPER_PACKAGED_AND_FIXTURE_TESTED
- App integration / new app updater: NOT_DONE / NONE
- Mac installation: NOT_INSTALLED
- London extraction/repack/runtime: NOT_TESTED_IN_THIS_WORK
- Model inference / LoRA: NOT_RUN / NOT_TRAINED

## User decision and continuity

London Seirei Tanteidan is the only required real-game pilot. The other game is deferred. Continue useful independent work while runtime is blocked; do not rewrite the installed app or infer its interfaces from reports. Preserve the requested three main sections: extraction/triage, translation/polish/QA, repack/test. Preserve Ollama role/model selections, FontKit v1.3.0, translations, revisions, glossary and resumable queues.

The user authorized continuation during active work. No background monitor, delayed retry or automatic later execution has been installed. The installed app remains v0.6.0 until an integrated tested updater is delivered.

## What was actually checked in this continuation

- Fresh read-only Container and Python probes both returned ClientError; no local game/app modifications were performed.
- GitHub checkpoint, source, tree, writes and GitHub Actions worked.
- Recursive repo tree at df0fc0f55e069348998213cf5d01c0c719a10050 did not contain the installed continue-retro-studio app implementation.
- Files located the original v0.6.0 ZIP: file_00000000998c8207a6736f19b3ff28a0, 1,324,541 bytes. A read returned zero readable lines. Source code inside this actual ZIP has NOT been inspected here.
- Expected ZIP hash was read from the existing Library checksum file file_00000000094882119ada8ea8f76a8e62: 02c3aa9f1102b5b00191c20f37e7c061bf225bc5c5305d40bb105560f1bc297e. This is a reference hash, NOT a freshly computed hash of that archive in this runtime.
- No ROM, BIOS, font assets, original/rebuilt BIN/CUE, user translations, database or private diagnostic headers were sent to GitHub/CI.

## Previous retained modules (unchanged in this continuation)

- studio_next/quality.py
- studio_next/test_quality.py
- studio_next/test_quality_hardening.py
- studio_next/review_payload.py
- studio_next/test_review_payload.py
- studio_next/README_TH.md
- studio_next/RESUME_REVIEW_TRANSPORT.md

Quality core: six-dimensional review validation, separate language/technical/human results, host-computed total, partial/unassessed scores, revision and policy/context fingerprints, blocking meaning issues, conservative token checks, unknown/stale technical states, suggestion-to-new-revision. It does not run a model, authenticate a human, migrate a database or implement the final game Build Gate.

Review input: bounded UTF-8 JSON object parsing; duplicate keys/escaped aliases, malformed Unicode, non-finite/oversized numbers, excessive nesting/nodes/strings, wrappers and trailing payload are rejected. Invalid AI response remains an input error, not a zero translation score. The finite-body reader does not implement the installed app's streaming HTTP envelope limits.

## New source-access recovery helper

Intent was recorded before writes in studio_next/RESUME_SOURCE_BRIDGE.md (commit d67a4181259f54d138c47629312818b95a0ee926). The successful outcome is recorded here; the intent journal is historical.

Added:
- studio_next/source_bridge.py
- studio_next/test_source_bridge.py
- studio_next/PREPARE_STUDIO_SOURCE.command
- studio_next/SOURCE_BRIDGE_README_TH.md
- studio_next/package_source_bridge.py

Updated .github/workflows/studio-quality-validation.yml to test and package only this helper alongside the prior isolated tests.

The helper runs on the user's Mac (Python 3.10+) against the exact original v0.6.0 app ZIP. It checks the pinned archive hash before reading members, validates member paths/duplicates/case collisions/symlinks/encoding/size limits, and emits allowlisted source as verbatim length-framed UTF-8 text with per-file SHA-256. It never executes archive code, scans installed PRIVATE data, uploads files or installs an app. It excludes ROM/BIOS/fonts/glyph data/models/databases/images/logs and binary fixtures. Only font-related program source (e.g. app/fontkit.py), not font assets, may be included.

Default output next to the selected original ZIP:
ContinueRetro_Source_Handoff_v0.6.0_02c3aa9f1102/
- CONTINUERETRO_V060_SOURCE.txt
- SOURCE_INDEX.json
- SHA256SUMS.txt

Existing identical results are reused without overwriting; different outputs are refused. Outputs use a same-parent temporary directory and rename. No missing destination directory is recreated as a substitute for a disconnected drive. The helper is not a secure OS sandbox; it avoids running archived code altogether.

The TXT is a source inspection handoff, NOT a complete runnable app export: unallowlisted assets/fixtures are omitted intentionally. Bundle hashes verify transfer integrity, not sender authentication or code safety. Before integrated app tests, review required omitted resources. Do not mistake fixture tests for inspection of the actual v0.6.0 ZIP.

## Exact retained test evidence

Historical quality core:
- Tested commit 1fc19ed176286caa93be6ea8dc86b73bac972c8a
- quality.py blob 7ee06c3965811cc5b25b6452942a48b050fad36e
- Run 34163214763 / Job 101869085421
- Log: Ran 62 tests in 0.010s / OK

Historical combined core + reviewer input:
- Tested commit 0008bbce2fe53abc64853fd8ec64ad4990bfb9ac
- Run 34177219061 / Job 101908911817
- Log: Ran 99 tests in 0.014s / OK

Latest tested code and helper package:
- Tested commit 3dcbe86ed459da1f78d3fdd223a279614b60410b
- Tree 5d1a986f4327c8bc3279c7d2ef6c0a5e5f95248e
- Run 34184111437 / Job 101928896246
- Final job status read through GitHub API: completed / success; all steps success
- Environment: Ubuntu 24.04.4, Python 3.12.3
- Full test log: Ran 131 tests in 0.076s / OK
- Composition: prior 99 tests actually re-run + 32 new source-bridge tests
- Packaged helper was extracted and its 32 tests re-run: Ran 32 tests in 0.062s / OK
- Package marker: PACKAGED_HELPER_FIXTURE_TESTS_PASS
- CI: https://github.com/originova05-arch/ContinueRetro-PS1/actions/runs/34184111437

These counts are isolated policy/input/source-transfer tests using authored fixtures, NOT the historical 136 Studio app tests. Do not sum the 32 packaged re-tests as 32 additional unique tests. They do not test native Finder behavior, real model inference, translation quality, London or app integration.

## Delivered helper artifact

- GitHub artifact ID: 10039903912
- Name: ContinueRetro-source-bridge-3dcbe86ed459da1f78d3fdd223a279614b60410b
- Download page: https://github.com/originova05-arch/ContinueRetro-PS1/actions/runs/34184111437/artifacts/10039903912
- Outer artifact size: 18,770 bytes
- Outer artifact SHA-256: 02a0c0292e485ab1d33e91b1b1fa14be633440e212583a85dcb1795fb7d4528a
- Inner helper ZIP: ContinueRetro_Source_Bridge_v1.zip
- Inner helper ZIP SHA-256: 33908f6a311874e23d88835f7ef31d0ec3f31f50c04b649300a74b9de6273959
- Artifact also contains the inner ZIP checksum file.
- Artifact metadata expiry: 2026-09-22T03:36:46Z; do not promise the GitHub artifact remains forever.
- Downloaded into this conversation through GitHub connector: file_00000000e51881f4be90f3d5367c3b4e, ContinueRetro_Source_Bridge_v1_Bundle.zip.
- Connector supplied a mounted path, but local filesystem confirmation is unavailable due to ClientError. Do not invent a sandbox link; use the actual conversation file reference.

This helper is NOT a new Studio version or installed update.

## User action that can unblock integration without the chat runtime

Open PREPARE_STUDIO_SOURCE.command from the unpacked helper and select the original ContinueRetro_Studio_ExternalDrive_v0.6.0.zip. The outer downloaded artifact contains the helper ZIP, so unpack until the launcher and source_bridge.py are visible together. Attach only CONTINUERETRO_V060_SOURCE.txt back in chat. No game/font/database upload, git command or Ollama reinstall is needed.

If source access/runtime becomes available independently, use the actual source directly; the handoff is a fallback, not a mandatory new application workflow.

## Integration responsibilities still outstanding

Inspect real v0.6.0 API/storage/worker/frontend before choosing integration points. review_payload.py is not called by the installed app yet. Limit outer HTTP body/NDJSON frames and accumulated content before allocation as well as final reviewer JSON; do not pass reasoning or the outer envelope as a review.

Host owns current fingerprints, context availability, model metadata, authenticated session/CSRF/actor actions, compare-and-swap writes, append-only history and game-specific validators. No UI controls, installed DB migrations, existing app installers or real game adapters were changed by this work.

## Game hashes, rollback and next transitions

- London Japanese BIN/CUE already supplied; do not request another game's upload to continue.
- Current-work London input SHA-256: NOT_COMPUTED; no output image or output SHA exists.
- Game files changed: NONE; LBA/raw-sector allowlist: NONE.
- Runtime QA: PENDING / NOT_RUN; no model training performed.
- Do not substitute an English-patched image for the Japanese base.
- Rollback: leave this unmerged source-only branch unused. Main, installed app, fonts, models and translations remain unchanged.

Next:
1. Read AGENTS.md and this checkpoint; probe execution once, not in an unchanged retry loop.
2. Receive/read the source TXT or restore direct ZIP execution; inspect actual modules and missing export resources.
3. Run baseline app tests where its sources/resources are available; integrate the existing core with real Reviewer path, state and DB.
4. Implement table/detail/queue UI using actual queries and separate quality/technical/human statuses, no mock dashboard.
5. For London, complete read-first/toolchain doctor gates, verify source hashes, identify one real format, implement adapter and validate no-op + controlled mutation + independent checks.
6. Only then create a new game image and test a named scene. Unknown codec/renderer/runtime evidence blocks release regardless of translation score.
