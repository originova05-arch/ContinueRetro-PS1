# Actual v0.6.0 source received — integration intent (2026-09-08)

Parent checkpoint: e8a34ae3d7c82317fa778dc0772e299936f64384.

The user returned CONTINUERETRO_V060_SOURCE.txt, conversation file file_00000000b2a08211b0a7a1cf1b90b718. Its header declares 59 source files, 701860 text bytes, original release archive SHA-256 02c3aa9f1102b5b00191c20f37e7c061bf225bc5c5305d40bb105560f1bc297e and source-index SHA-256 45f323dc1d364540973979b00637c6e2e3ee8dcfc2a7a0982148e37a0156a4da. The header is not a fresh independent hash computation. Files can now read the implementation. Container/Python and the user-visible execution route still return ClientError. No repeat request for the source bridge or game files is needed.

Read actual ai_client.py, ai_pipeline.py, ai_store.py, server.py, studio_storage.py, translation.py, workflow.py and frontend/workbench code, not just release notes. Actual baseline: stdlib Python ThreadingHTTPServer + SQLite/WAL + multiprocessing worker + plain JS/CSS. Model chat is bounded finite JSON (stream=False), not NDJSON. work_items and cr5_queue are canonical working state; legacy text_entries must not be scanned to paint the UI. The old QA mixes linguistic issues and format checks and treats missing codec/layout as warnings; new reporting must keep UNKNOWN distinct without representing legacy QA as full binary readiness.

Plan:
1. Preserve readable baseline sources/test excerpts with their declared hashes and verification scope. Verify any reconstructed source before claiming byte identity. No private game/font/model/database assets in GitHub.
2. Add persistent review/technical/human events and freshness checks as additive cr7_* tables. Integrate the existing quality and bounded-input modules with the actual Reviewer client and job path. Host computes totals, commits against source/target/revision/context/rubric fingerprints and never lets AI set human approval.
3. Add server-side quality queries/detail endpoints and real asynchronous review jobs using existing JobManager/queue. Keep legacy translation and build functionality; do not replace unknown codec/renderer with fake PASS.
4. Incrementally replace only the translation view with a compact table, separate Score/Tech/Human columns and right detail pane, keep three visible stages, and move verbose task details below the work area. Reuse existing source/FontKit/build endpoints. All enabled controls need an implemented backend path.
5. Build a hash-checked additive updater that preserves installed assets and can test the actual baseline on the user's machine before activation; never claim unrun full-app/real-model/London tests.
6. Record exact CI commit/tests and observed integration boundary before delivering. Full real London adapter/repack/runtime remains a separate pending gate until game tools/runtime are available.

This journal records intent, not completion. The installed app remains v0.6.0; main and user data are unchanged.
