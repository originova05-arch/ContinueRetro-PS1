# Source-access recovery intent — 2026-09-08

Parent checkpoint commit: df0fc0f55e069348998213cf5d01c0c719a10050.

Fresh read-only Container and Python probes both returned ClientError. GitHub checkpoint/source reads succeeded. Files located the v0.6.0 ZIP (file_00000000998c8207a6736f19b3ff28a0), but reading it returned zero readable lines. No v0.6.0 implementation has been inspected in this continuation. Do not reconstruct app APIs from release reports or old chat snippets.

Verified reference: the Library checksum file file_00000000094882119ada8ea8f76a8e62 records SHA-256 02c3aa9f1102b5b00191c20f37e7c061bf225bc5c5305d40bb105560f1bc297e for ContinueRetro_Studio_ExternalDrive_v0.6.0.zip. This is the expected release hash, NOT a hash recomputed from the archive in this runtime.

Next retained task: build a source-only, offline recovery helper that runs on the user's Mac against that exact release ZIP. It should emit a readable UTF-8 source bundle that Files can inspect even when the chat execution runtime is unavailable. Validate archive identity, safe member paths, text boundaries and hashes. Do not execute archived code, inspect the installed PRIVATE directory, overwrite any existing output, or upload anything. Exclude ROM/BIOS/font/model/database/binary assets and logs. Keep the baseline archive untouched.

Test the helper with authored ZIP fixtures in GitHub Actions, then package only the helper/launcher/instructions. Tests on fixtures must not be described as inspection of the real v0.6.0 archive or London validation. Record the exact tested commit/job/log before saying tests passed. The prior 99 quality/input tests remain a separate existing scope and should be re-run, not merely added numerically.

UI integration and London remain blocked on actual source/data access. The helper is not a Studio updater and does not install or train a model. Main, the external-drive app, Japanese London images, FontKit and user translations are unchanged. London is the only game pilot; the other game remains deferred.

Outcome: IN_PROGRESS. See CHECKPOINT_LATEST.md for the last retained test results until this journal is updated.
