# CHECKPOINT — London-first / Studio Quality Core

Updated: 2026-09-08 (Thailand)

## Status

- Repository: originova05-arch/ContinueRetro-PS1
- Work branch: studio/london-quality-checkpoint-20260908
- Main branch: not modified by this work
- Existing user app baseline: ContinueRetro Studio v0.6.0
- This work: ISOLATED_CORE_AND_REVIEW_INPUT_BOUNDARY_UNIT_TESTED
- App integration: NOT_INTEGRATED
- Mac installation: NOT_INSTALLED
- London extraction/repack/runtime: NOT_TESTED_IN_THIS_WORK
- Model inference / LoRA: NOT_RUN / NOT_TRAINED

## User decision / scope

London Seirei Tanteidan is the only required real-game pilot for the next step. The other game is deferred and must not block progress. Continue other independent modules if real-game/runtime tests remain unavailable. Do not restart the application project or replace working backend code solely for a UI redesign.

User authorized continuing as soon as execution is available during active work. No background monitor, scheduled retry or delayed automatic resumption has been installed. Do not imply this chat is monitoring runtime after responding.

Retain the three primary sections requested by the user: extraction/triage, translation/polish/QA, repack/test. Retain Ollama roles and installed model selections, FontKit v1.3.0, translations, revisions, glossary, and existing resumable queues.

## What actually worked and failed

- Container and Python each received a fresh read-only probe in this continuation; both still returned ClientError. These probes performed no intended writes.
- Previous turn: the v0.6.0 release report was readable; ZIP text extraction returned no readable source content. Source inspection and integration must not be inferred from reports.
- GitHub connector: checkpoint/source reads and isolated-branch source writes succeeded.
- Earlier repo tree inspection did not expose the continue-retro-studio source from the attached v0.6.0 ZIP. Do not pretend this staging core is already integrated into that app.
- GitHub Actions ran source-only tests again. No ROM, CUE, BIOS, FontKit, user translations or private diagnostic headers were uploaded.

## Retained source

Existing:
- studio_next/quality.py
- studio_next/test_quality.py
- studio_next/test_quality_hardening.py
- studio_next/README_TH.md
- .github/workflows/studio-quality-validation.yml

Added in this continuation:
- studio_next/review_payload.py
- studio_next/test_review_payload.py
- studio_next/RESUME_REVIEW_TRANSPORT.md (pre-write intent journal; latest outcome is recorded here)

The unchanged quality core implements six-dimensional review validation; independent language/technical/human results; host-computed totals; partial scoring; identity/fingerprint freshness; issue blocking; conservative named-placeholder/printf checks; unassessed/stale technical states; and suggestion-to-new-revision behavior. It does not run an AI, authenticate a human action, migrate a database, or make a complete Build Gate.

The new review input boundary accepts one bounded UTF-8 JSON object, rejects duplicate keys including escaped aliases, non-finite numbers, oversized numeric tokens, excessive nesting/nodes/strings, malformed Unicode, markdown/reasoning wrappers and trailing payloads. A finite binary-stream helper reads at most the configured byte limit plus one and does not retry I/O failures. parse_review_response then calls the existing quality.parse_review identity/schema/range checks. Invalid model output raises InvalidReview rather than becoming a zero score or technical failure of the translation.

## Exact retained validation evidence

Previous core validation, preserved:
- Tested code-and-tests commit: 1fc19ed176286caa93be6ea8dc86b73bac972c8a
- quality.py Git blob: 7ee06c3965811cc5b25b6452942a48b050fad36e (not modified in this continuation)
- Workflow run: 34163214763 / Job: 101869085421
- Observed log: Ran 62 tests in 0.010s / OK

Latest combined isolated validation:
- Tested code-and-tests commit: 0008bbce2fe53abc64853fd8ec64ad4990bfb9ac
- Workflow run: 34177219061
- Job: 101908911817
- Job conclusion read through GitHub API: success
- Test log read: Ran 99 tests in 0.014s / OK
- Composition: previous 62 tests re-run plus 37 new payload/input-boundary tests
- Environment observed: Ubuntu 24.04.4, Python 3.12.3
- CI URL: https://github.com/originova05-arch/ContinueRetro-PS1/actions/runs/34177219061

These are isolated deterministic-policy/input tests using authored fixtures. They do not include the historical 136 Studio tests and do not prove model quality, real-game extraction, runtime behavior or end-to-end app integration. Documentation-only commits after the tested commit do not change the tested source; re-run validation after source changes.

## Integration boundary still outstanding

review_payload.py is not called by the installed app's HTTP client. Before wiring it in, inspect actual v0.6.0 source. The host must cap the OUTER HTTP envelope and accumulated streaming content too; rejecting a previously allocated oversized string does not retroactively cap network memory. read_json_object is for a finite binary body, not an unbounded NDJSON stream. Only the final message.content is review input; never pass model reasoning or the outer Ollama envelope as the review itself.

Host-owned responsibilities remain: current context and rubric fingerprints, bounded prompt/output, service-failure routing, authentication/CSRF for human actions, transaction/compare-and-swap writes, append-only history, independent game validators and final Build/runtime gates. No UI controls, database schema or app installer have been changed by these isolated modules.

## Game data / hashes / rollback

- Pilot inputs: user-provided London Seirei Tanteidan (Japan).cue and .bin; Japanese ZIP also exists in conversation/library context.
- Input BIN SHA-256 for this work: NOT_COMPUTED (runtime unavailable).
- Game output SHA-256: NONE (no game output created).
- Files in game modified: NONE.
- LBA/raw-sector allowlist: NONE.
- Runtime QA: PENDING / NOT_RUN.
- Do not substitute an English-patched London image for the Japanese original without an explicit recorded reason and separate hashes.
- Rollback: leave this unmerged branch unused; main and the external-drive app have not been changed. Do not delete existing app/project data.

## Next safe transitions

1. Read AGENTS.md, this checkpoint and README_TH.md. Preserve the work branch and original files. Probe runtime once before assuming recovery; avoid unchanged retry loops.
2. Restore execution/access to the attached v0.6.0 ZIP; inspect actual source, API, storage schema and worker entry points before integration. Do not infer interfaces solely from release reports.
3. Run the existing Studio regression tests; wire the review input boundary and quality core into the real Reviewer path with transport limits, session/CSRF for human actions, compare-and-swap revision commits and append-only review history.
4. Implement the requested table/detail/queue UI against current database queries, with separate score/technical/human status. No mock dashboard data or inert production buttons.
5. For real London work, complete the repository toolchain read-first/doctor gates; verify CUE/BIN hashes and identify a real file format; implement/test an adapter with no-op round-trip plus controlled mutation and independent checks.
6. Only after codec/renderer/build requirements are proved, create a new image and test a named scene. Unknown requirements block release, regardless of language score.

No user action or another game's upload is required merely to retain this checkpoint. The installed app remains v0.6.0 until a real integrated updater is tested and delivered.
