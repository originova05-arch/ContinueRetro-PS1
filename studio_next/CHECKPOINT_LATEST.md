# CHECKPOINT — London-first / Studio Quality Core

Recorded: 2026-09-08 (Thailand)

## Status

- Repository: originova05-arch/ContinueRetro-PS1
- Work branch: studio/london-quality-checkpoint-20260908
- Main branch: not modified by this work
- Existing user app baseline: ContinueRetro Studio v0.6.0
- This work: ISOLATED_CORE_IMPLEMENTED_AND_UNIT_TESTED
- App integration: NOT_INTEGRATED
- Mac installation: NOT_INSTALLED
- London extraction/repack/runtime: NOT_TESTED_IN_THIS_WORK
- Model inference / LoRA: NOT_RUN / NOT_TRAINED

## User decision / scope

London Seirei Tanteidan is the only required real-game pilot for the next step. The other game is deferred and must not block progress. Continue other independent modules if real-game/runtime tests remain unavailable. Do not restart the application project or replace working backend code solely for a UI redesign.

Retain the three primary sections requested by the user: extraction/triage, translation/polish/QA, repack/test. Retain Ollama roles and installed model selections, FontKit v1.3.0, translations, revisions, glossary, and existing resumable queues.

## What actually worked and failed

- Container execution: ClientError on the environment probe in this turn.
- Python execution: ClientError on the independent probe in this turn.
- Files: the v0.6.0 release report is readable; ZIP text extraction returned no readable source content.
- GitHub connector: repository read, isolated branch creation, source writes and Actions reads succeeded.
- Repo tree inspection did not expose the continue-retro-studio source from the attached v0.6.0 ZIP. Do not pretend this staging module is already integrated into that app.
- GitHub Actions ran the source-only quality tests. No ROM, CUE, BIOS, FontKit, user translations or private diagnostic headers were uploaded.

## Retained source

- studio_next/quality.py
- studio_next/test_quality.py
- studio_next/test_quality_hardening.py
- studio_next/README_TH.md
- studio_next/CHECKPOINT_LATEST.md
- .github/workflows/studio-quality-validation.yml

The module implements six-dimensional review validation; independent language/technical/human results; host-computed totals; partial scoring; identity/fingerprint freshness; issue blocking; conservative named-placeholder/printf checks; unassessed/stale technical states; and suggestion-to-new-revision behavior. It does not run an AI, authenticate a human action, migrate a database, or make a complete Build Gate.

## Exact retained validation evidence

- Tested code-and-tests commit: 1fc19ed176286caa93be6ea8dc86b73bac972c8a
- quality.py Git blob: 7ee06c3965811cc5b25b6452942a48b050fad36e
- Workflow run: 34163214763
- Job: 101869085421
- Job conclusion observed through GitHub API: success
- Test log observed: Ran 62 tests in 0.010s / OK
- Environment observed: Ubuntu 24.04.4, Python 3.12.3
- CI URL: https://github.com/originova05-arch/ContinueRetro-PS1/actions/runs/34163214763

The 62 tests are isolated deterministic-policy tests using authored fixtures. They do not include the historical 136 Studio tests and do not prove model quality, real-game extraction, runtime behavior or end-to-end app integration. Later documentation-only commits do not change the tested module; validate again after code changes.

## Game data / hashes / rollback

- Pilot inputs: user-provided London Seirei Tanteidan (Japan).cue and .bin; Japanese ZIP also exists in the conversation/library context.
- Input BIN SHA-256 for this work: NOT_COMPUTED (runtime unavailable).
- Game output SHA-256: NONE (no game output created).
- Files in game modified: NONE.
- LBA/raw-sector allowlist: NONE.
- Runtime QA: PENDING / NOT_RUN.
- Do not substitute an English-patched London image for the Japanese original without an explicit recorded reason and separate hashes.
- Rollback: leave this unmerged branch unused; main and the external-drive app have not been changed by this work. Do not delete existing app/project data.

## Next safe transitions

1. Read AGENTS.md, this checkpoint and README_TH.md. Preserve work branch and original game files.
2. Restore execution/access to the attached v0.6.0 ZIP; inspect actual source, API, storage schema and worker entry points before integrating. Do not infer interfaces solely from release reports.
3. Run existing Studio regression tests; add core to the actual reviewer path with bounded JSON loading, authentication/CSRF for human actions, compare-and-swap revision commits and append-only review history.
4. Implement the requested table/detail/queue UI against actual current database queries, with separate score/technical/human status. No mocked dashboard numbers or inert production buttons.
5. For real London work, complete the repo toolchain read-first/doctor gates; verify CUE/BIN hashes and identify a real file format; implement/test an adapter on that file using no-op round-trip plus controlled mutation and independent checks.
6. Only after codec/renderer/build requirements are proved, create a new image and test a named scene. Unknown requirements block release; they never become PASS because the score is high.

No user action or another game's upload is required merely to retain this checkpoint. The app remains v0.6.0 until a real integrated updater is tested and delivered.
