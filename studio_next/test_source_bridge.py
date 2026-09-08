"""Source-bridge tests use authored ZIP fixtures, never a ROM or user archive."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import source_bridge as sb


ROOT = "ContinueRetro_Studio_ExternalDrive_v0.6.0"
APP = "payload/apps/continue-retro-studio/"
BASE_FILES = [
    (APP + "app/server.py", b'"""Authored fixture, not the production app."""\nvalue = 1\n'),
    (APP + "app/static/index.html", "<!doctype html><title>ทดสอบซอร์ส</title>\n".encode()),
    (APP + "app/static/app.js", b"console.log('source only');\n"),
    (APP + "app/static/styles.css", b"body { margin: 0; }\n"),
    (APP + "config/app.defaults.json", b'{"version":"fixture"}\n'),
    (APP + "knowledge/rules.json", b'{"rules":["authored fixture"]}\n'),
    (APP + "tests/test_authored.py", b"# Authored test; no game bytes.\n"),
    ("install_to_external_drive.py", b"# Kept as text, never executed.\n"),
]


def fixture(entries=(), *, base=True):
    out = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for path, value in (BASE_FILES if base else []):
                archive.writestr(ROOT + "/" + path, value)
            for path, value in entries:
                archive.writestr(path, value)
    blob = out.getvalue()
    return blob, sb.ReleaseSpec("0.6.0", sb.digest(blob), ROOT)


class SourceBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-bridge-fixture-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, entries=(), **kwargs):
        blob, spec = fixture(entries, **kwargs)
        path = self.root / "release fixture.zip"
        path.write_bytes(blob)
        return path, spec

    def test_pinned_release_identity_is_explicit(self):
        self.assertEqual(sb.BASELINE.version, "0.6.0")
        self.assertEqual(sb.BASELINE.archive_sha256,
                         "02c3aa9f1102b5b00191c20f37e7c061bf225bc5c5305d40bb105560f1bc297e")

    def test_valid_source_survives_bundle_byte_for_byte(self):
        blob, spec = fixture()
        index, rows = sb.inspect_release_bytes(blob, spec)
        meta, decoded = sb.parse_bundle(sb.render_bundle(index, rows))
        self.assertEqual(rows, decoded)
        self.assertEqual(meta["archive_sha256"], sb.digest(blob))
        self.assertFalse(meta["archive_code_executed"])
        self.assertFalse(meta["runnable_app_export"])
        self.assertFalse(meta["uploaded"])
        self.assertEqual(meta["file_count"], len(BASE_FILES))

    def test_wrong_archive_hash_rejected_before_zip_inspection(self):
        blob, spec = fixture()
        with patch.object(sb.zipfile, "ZipFile", side_effect=AssertionError("must not open ZIP")):
            with self.assertRaises(sb.RecoveryError):
                sb.inspect_release_bytes(blob, replace(spec, archive_sha256="0" * 64))

    def test_default_does_not_accept_fixture_as_real_release(self):
        blob, _ = fixture()
        with self.assertRaises(sb.RecoveryError):
            sb.inspect_release_bytes(blob)

    def test_member_paths_reject_escape_windows_and_ambiguity(self):
        for name in ("../outside.py", "/absolute.py", "C:/escape.py", "A\\x.py",
                     ROOT + "//x.py", ROOT + "/./x.py", ROOT + "/../x.py",
                     ROOT + "/bad\tname.py", ROOT + "/e\u0301.py"):
            with self.subTest(name=name):
                blob, spec = fixture([(name, b"x")])
                with self.assertRaises(sb.RecoveryError):
                    sb.inspect_release_bytes(blob, spec)

    def test_safe_path_rejects_nul_and_directory_traversal(self):
        for name in ("x\0tail", "a/../", "a///", "", "/"):
            with self.subTest(name=name), self.assertRaises(sb.RecoveryError):
                sb.safe_path(name, directory=True)

    def test_other_package_root_rejected(self):
        blob, spec = fixture([("OTHER/app/server.py", b"x")])
        with self.assertRaises(sb.RecoveryError):
            sb.inspect_release_bytes(blob, spec)

    def test_duplicate_and_case_collision_rejected(self):
        original = ROOT + "/" + APP + "app/server.py"
        for name in (original, original.replace("server.py", "SERVER.PY")):
            with self.subTest(name=name):
                blob, spec = fixture([(name, b"another")])
                with self.assertRaises(sb.RecoveryError):
                    sb.inspect_release_bytes(blob, spec)

    def test_file_directory_collision_rejected(self):
        blob, spec = fixture([(ROOT + "/payload/apps", b"not a directory")])
        with self.assertRaises(sb.RecoveryError):
            sb.inspect_release_bytes(blob, spec)

    def test_symlink_and_fifo_rejected(self):
        for kind in (stat.S_IFLNK, stat.S_IFIFO):
            with self.subTest(kind=kind):
                info = zipfile.ZipInfo(ROOT + "/" + APP + "app/link.py")
                info.create_system = 3
                info.external_attr = (kind | 0o644) << 16
                blob, spec = fixture([(info, b"../../outside")])
                with self.assertRaises(sb.RecoveryError):
                    sb.inspect_release_bytes(blob, spec)

    def test_encrypted_header_rejected(self):
        blob, _ = fixture()
        data = bytearray(blob)
        local = data.index(b"PK\x03\x04")
        central = data.index(b"PK\x01\x02")
        data[local + 6] |= 1
        data[central + 8] |= 1
        blob = bytes(data)
        spec = sb.ReleaseSpec("0.6.0", sb.digest(blob), ROOT)
        with self.assertRaises(sb.RecoveryError):
            sb.inspect_release_bytes(blob, spec)

    def test_omit_font_game_model_database_images_and_secrets(self):
        omitted = [
            "PRIVATE/roms/game.bin", "PRIVATE/studio/studio.sqlite3",
            APP + "app/static/font.woff2", APP + "app/assets/atlas.json",
            APP + "app/fonts/glyph.py", APP + "knowledge/glyph-metrics.json",
            APP + "knowledge/credentials.json", APP + "knowledge/.env.local",
            APP + "tests/fixture.bin", APP + "tests/font.bdf",
            APP + "tests/data.json", APP + "QA/server.log",
            APP + "app/.git/config", "QA/screenshot.png", "models/model.gguf",
        ]
        blob, spec = fixture([(ROOT + "/" + p, b"PRIVATE_SENTINEL") for p in omitted])
        index, rows = sb.inspect_release_bytes(blob, spec)
        self.assertEqual(len(rows), len(BASE_FILES))
        self.assertEqual({x["path"] for x in index["omitted"]}, set(omitted))
        self.assertNotIn(b"PRIVATE_SENTINEL", sb.render_bundle(index, rows))

    def test_fontkit_python_module_is_code_not_a_font_asset(self):
        path = APP + "app/fontkit.py"
        self.assertTrue(sb.source_selection(path)[0])
        self.assertFalse(sb.source_selection(APP + "knowledge/FONTKIT.json")[0])
        self.assertFalse(sb.source_selection(APP + "app/static/thai87.bin")[0])

    def test_archive_member_and_total_limits(self):
        blob, spec = fixture()
        for name, value in (("MAX_ARCHIVE", len(blob) - 1), ("MAX_MEMBERS", 2),
                            ("MAX_MEMBER", 8), ("MAX_TEXT", 20)):
            with self.subTest(limit=name), patch.object(sb, name, value):
                with self.assertRaises(sb.RecoveryError):
                    sb.inspect_release_bytes(blob, spec)

    def test_invalid_selected_text_rejected(self):
        for raw in (b"\xffbad utf8", b"x\0y", b"bad\x01control"):
            with self.subTest(raw=raw):
                blob, spec = fixture([(ROOT + "/" + APP + "app/invalid.py", raw)])
                with self.assertRaises(sb.RecoveryError):
                    sb.inspect_release_bytes(blob, spec)

    def test_required_entrypoints_not_inferred_from_filename(self):
        blob, spec = fixture([(ROOT + "/README_TH.md", b"not source")], base=False)
        with self.assertRaises(sb.RecoveryError):
            sb.inspect_release_bytes(blob, spec)

    def test_not_zip_and_truncated_zip_rejected(self):
        good, _ = fixture()
        for blob in (b"not zip", good[:len(good) // 2]):
            spec = sb.ReleaseSpec("0.6.0", sb.digest(blob), ROOT)
            with self.subTest(length=len(blob)), self.assertRaises(sb.RecoveryError):
                sb.inspect_release_bytes(blob, spec)

    def test_crlf_bom_no_final_newline_and_markers_preserved(self):
        raw = '\ufeff# ไทย\r\nvalue = "@@END"\n@@FILE dummy\n'.encode()
        blob, spec = fixture([(ROOT + "/" + APP + "app/marker.py", raw)])
        index, rows = sb.inspect_release_bytes(blob, spec)
        _, decoded = sb.parse_bundle(sb.render_bundle(index, rows))
        found = next(r for r in decoded if r["path"].endswith("marker.py"))
        self.assertEqual(found["content"].encode(), raw)
        self.assertEqual(found["sha256"], hashlib.sha256(raw).hexdigest())

    def test_bundle_tampering_truncation_and_trailing_data_rejected(self):
        blob, spec = fixture()
        index, rows = sb.inspect_release_bytes(blob, spec)
        bundle = sb.render_bundle(index, rows)
        for changed in (bundle.replace(b"value = 1", b"value = 2"), bundle[:-4], bundle + b"TRAILER"):
            with self.subTest(length=len(changed)), self.assertRaises(sb.RecoveryError):
                sb.parse_bundle(changed)

    def test_bundle_wrong_count_size_and_index_rejected(self):
        blob, spec = fixture()
        index, rows = sb.inspect_release_bytes(blob, spec)
        bundle = sb.render_bundle(index, rows)
        for changed in (
            bundle.replace(b'"file_count":8', b'"file_count":true', 1),
            bundle.replace(b'"file_count":8', b'"file_count":9', 1),
            bundle.replace(index["source_index_sha256"].encode(), b"0" * 64, 1),
            bundle.replace(b'"size_bytes":', b'"size_bytes":-1,"bad":', 1),
        ):
            with self.subTest(changed=changed[:120]), self.assertRaises(sb.RecoveryError):
                sb.parse_bundle(changed)

    def test_bundle_duplicate_header_key_rejected(self):
        blob, spec = fixture()
        index, rows = sb.inspect_release_bytes(blob, spec)
        bundle = sb.render_bundle(index, rows)
        bundle = bundle.replace(b'"file_count":8', b'"file_count":8,"file_count":8', 1)
        with self.assertRaises(sb.RecoveryError):
            sb.parse_bundle(bundle)

    def test_render_refuses_changed_content(self):
        blob, spec = fixture()
        index, rows = sb.inspect_release_bytes(blob, spec)
        rows[0]["content"] += "changed"
        with self.assertRaises(sb.RecoveryError):
            sb.render_bundle(index, rows)

    def test_prepare_preserves_source_and_installed_private_data(self):
        source, spec = self.archive()
        original = source.read_bytes()
        private = self.root / "ContinueRetro-PS1" / "PRIVATE"
        private.mkdir(parents=True)
        sentinel = private / "studio.sqlite3"
        sentinel.write_bytes(b"USER_DATABASE_UNTOUCHED")
        result = sb.prepare(source, spec=spec)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(sentinel.read_bytes(), b"USER_DATABASE_UNTOUCHED")
        self.assertEqual(set(p.name for p in Path(result["directory"]).iterdir()),
                         {sb.BUNDLE_NAME, sb.INDEX_NAME, sb.SUMS_NAME})
        self.assertEqual(result["file_count"], len(BASE_FILES))
        self.assertFalse(result["reused"])

    def test_prepare_is_idempotent_without_overwriting(self):
        source, spec = self.archive()
        result = sb.prepare(source, spec=spec)
        output = Path(result["bundle"])
        before = output.stat().st_mtime_ns
        again = sb.prepare(source, spec=spec)
        self.assertTrue(again["reused"])
        self.assertEqual(output.stat().st_mtime_ns, before)

    def test_prepare_rejects_changed_existing_output(self):
        source, spec = self.archive()
        result = sb.prepare(source, spec=spec)
        output = Path(result["bundle"])
        output.write_bytes(b"USER_EDIT")
        with self.assertRaises(sb.RecoveryError):
            sb.prepare(source, spec=spec)
        self.assertEqual(output.read_bytes(), b"USER_EDIT")

    def test_prepare_rejects_symlink_output(self):
        source, spec = self.archive()
        result = sb.prepare(source, spec=spec)
        output = Path(result["bundle"])
        saved = output.read_bytes()
        output.unlink()
        outside = self.root / "unrelated.txt"
        outside.write_bytes(saved)
        try:
            output.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable on this test host")
        with self.assertRaises(sb.RecoveryError):
            sb.prepare(source, spec=spec)
        self.assertEqual(outside.read_bytes(), saved)

    def test_missing_destination_does_not_create_replacement_mount(self):
        source, spec = self.archive()
        missing = self.root / "MissingDrive"
        with self.assertRaises(sb.RecoveryError):
            sb.prepare(source, missing, spec=spec)
        self.assertFalse(missing.exists())

    def test_code_in_archive_is_not_executed(self):
        marker = self.root / "EXECUTED"
        code = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nraise RuntimeError('must not run')\n"
        source, spec = self.archive([(ROOT + "/" + APP + "app/evil.py", code)])
        sb.prepare(source, spec=spec)
        self.assertFalse(marker.exists())

    def test_interrupted_output_cleans_only_own_temporary_directory(self):
        source, spec = self.archive()
        keep = self.root / "KEEP.txt"
        keep.write_text("user file")
        with patch.object(sb.os, "fsync", side_effect=OSError("fixture disk failure")):
            with self.assertRaises(OSError):
                sb.prepare(source, spec=spec)
        self.assertEqual(keep.read_text(), "user file")
        self.assertEqual(list(self.root.glob(".continue-retro-source-*")), [])
        self.assertEqual(list(self.root.glob("ContinueRetro_Source_Handoff*")), [])

    def test_cli_cancel_and_wrong_hash_do_not_write(self):
        with patch.object(sb, "choose_archive", return_value=None), redirect_stdout(io.StringIO()):
            self.assertEqual(sb.main([]), 0)
        source, _ = self.archive()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(sb.main(["--zip", str(source)]), 1)
        self.assertEqual(list(self.root.glob("ContinueRetro_Source_Handoff*")), [])

    def test_cli_has_no_unpinned_archive_override(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            sb.main(["--expected-sha256", "0" * 64])
        self.assertNotEqual(error.exception.code, 0)

    def test_import_and_library_functions_do_not_open_network(self):
        blob, spec = fixture()
        import socket
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            index, rows = sb.inspect_release_bytes(blob, spec)
            sb.parse_bundle(sb.render_bundle(index, rows))


if __name__ == "__main__":
    unittest.main(verbosity=2)
