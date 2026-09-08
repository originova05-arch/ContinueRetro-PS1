#!/usr/bin/env python3
"""Read-only source handoff for the pinned ContinueRetro Studio v0.6.0 ZIP.

This is not an updater or a game extractor. It never imports or executes archive
members, scans the installed app, uploads files, or reads a PRIVATE directory.
The generated UTF-8 bundle is readable by the Files connector without unzipping.
Python 3.10+, standard library only.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile


class RecoveryError(ValueError):
    """No source was installed or uploaded when this exception is raised."""


@dataclass(frozen=True)
class ReleaseSpec:
    version: str
    archive_sha256: str
    package_root: str


BASELINE = ReleaseSpec(
    "0.6.0",
    "02c3aa9f1102b5b00191c20f37e7c061bf225bc5c5305d40bb105560f1bc297e",
    "ContinueRetro_Studio_ExternalDrive_v0.6.0",
)
MAX_ARCHIVE = 16 * 1024 * 1024
MAX_MEMBER = 2 * 1024 * 1024
MAX_TEXT = 24 * 1024 * 1024
MAX_MEMBERS = 5000
MAX_HEADER = 4096
MAGIC = b"CONTINUERETRO_SOURCE_BUNDLE_V1\n"
BUNDLE_NAME = "CONTINUERETRO_V060_SOURCE.txt"
INDEX_NAME = "SOURCE_INDEX.json"
SUMS_NAME = "SHA256SUMS.txt"
APP_PREFIX = "payload/apps/continue-retro-studio/"
DENIED_DIRS = frozenset({
    "private", ".git", "__macosx", "__pycache__", "node_modules", ".venv",
    "venv", "fontkits", "fonts", "glyphs", "bios", "roms", "models", "logs",
    "screenshots", "backups", "installer-backups", "checkpoints", "qa",
})
BINARY_SUFFIXES = frozenset({
    ".bin", ".cue", ".iso", ".img", ".rom", ".chd", ".cso", ".zso",
    ".bdf", ".pcf", ".fnt", ".fon", ".ttf", ".otf", ".woff", ".woff2",
    ".gguf", ".safetensors", ".pt", ".pth", ".onnx", ".tflite",
    ".sqlite", ".sqlite3", ".db", ".wal", ".shm", ".har", ".log",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".zip", ".7z",
    ".exe", ".dll", ".dylib", ".so", ".pyc", ".pyo",
})
ROOT_FILES = frozenset({
    "install_to_external_drive.py", "INSTALL_TO_EXTERNAL_DRIVE.command",
    "UPDATE_STUDIO.command", "README_TH.md", "VERSION", "REQUIRED_FONTKIT.txt",
    "payload/START_CONTINUE_RETRO_STUDIO.command",
    "payload/START_OLLAMA_EXTERNAL.command", "payload/SETUP_OLLAMA_EXTERNAL.command",
})
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def safe_path(name: str, *, directory: bool = False) -> str:
    """Reject ambiguous POSIX/Windows/Unicode member names, even if excluded."""
    if not isinstance(name, str) or not name or len(name) > 1024:
        raise RecoveryError("ชื่อไฟล์ภายใน ZIP ว่างหรือยาวเกินกำหนด")
    if "\\" in name or ":" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise RecoveryError("ZIP มีชื่อไฟล์ไม่ปลอดภัยหรืออักขระควบคุม")
    if unicodedata.normalize("NFC", name) != name:
        raise RecoveryError("ชื่อไฟล์ Unicode ไม่อยู่ในรูปแบบ NFC")
    value = name[:-1] if directory and name.endswith("/") else name
    if not value or value.startswith("/") or any(p in ("", ".", "..") for p in value.split("/")):
        raise RecoveryError("ZIP มี absolute path, path traversal หรือชื่อซ้ำซ้อน")
    if PurePosixPath(value).as_posix() != value:
        raise RecoveryError("พาธภายใน ZIP ไม่เป็น canonical path")
    return value


def source_selection(relative: str) -> tuple[bool, str]:
    """Allow code/text in known release source locations, never font/binary assets."""
    relative = safe_path(relative)
    p = PurePosixPath(relative)
    lower = p.name.casefold()
    if any(part.casefold() in DENIED_DIRS for part in p.parts[:-1]):
        return False, "private/cache/asset/report directory"
    if p.suffix.casefold() in BINARY_SUFFIXES or lower.endswith(("-wal", "-shm")):
        return False, "binary/font/model/database/image/log asset"
    if lower.startswith(".env") or lower in {"credentials.json", "secrets.json", "cookies.txt", "token.txt"}:
        return False, "credential-like filename"
    # Font code is source; bitmap/metrics/atlas data is not transferred.
    if p.suffix.casefold() in {".json", ".csv", ".txt"} and any(
            token in lower for token in ("glyph", "fontkit", "font-metric", "atlas", "thai87")):
        return False, "font data is excluded"
    if relative in ROOT_FILES:
        return True, "release entrypoint/document"
    if not relative.startswith(APP_PREFIX):
        return False, "outside application source allowlist"
    tail = PurePosixPath(relative[len(APP_PREFIX):])
    if len(tail.parts) == 1 and tail.name in {"README_TH.md", "RUN_SELF_TEST.command", "pyproject.toml", "requirements.txt"}:
        return True, "application metadata"
    if tail.parts[0] == "app":
        if tail.suffix == ".py":
            return True, "Python implementation"
        if len(tail.parts) >= 3 and tail.parts[1] == "static" and tail.suffix in {".html", ".css", ".js", ".mjs", ".ts", ".tsx", ".jsx"}:
            return True, "web implementation"
    if tail.parts[0] == "tests" and tail.suffix == ".py":
        return True, "authored Python tests; data fixtures excluded"
    if tail.parts[0] in {"config", "knowledge"} and tail.suffix in {".json", ".md", ".txt", ".toml", ".yaml", ".yml"}:
        return True, "configuration or authored knowledge text"
    return False, "not in source allowlist (not a complete runnable app export)"


def inspect_release_bytes(blob: bytes, spec: ReleaseSpec = BASELINE) -> tuple[dict, list[dict]]:
    """Only a caller-trusted ReleaseSpec is accepted; CLI exposes no hash override."""
    if not isinstance(blob, bytes) or not blob or len(blob) > MAX_ARCHIVE:
        raise RecoveryError("ZIP ว่างหรือเกินขีดจำกัด 16 MiB ของตัวเตรียมซอร์ส")
    if HASH_RE.fullmatch(spec.archive_sha256) is None or digest(blob) != spec.archive_sha256:
        raise RecoveryError("SHA-256 ไม่ตรง ZIP v0.6.0 ที่บันทึกไว้ จึงไม่อ่านหรือส่งออกเนื้อหา กรุณาเลือกแพ็กต้นฉบับเดิม")
    records, omitted, total = [], [], 0
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_MEMBERS:
                raise RecoveryError("ZIP มีรายการมากเกินขอบเขต")
            seen, files, directories, entries = set(), set(), set(), []
            for info in infos:
                # orig_filename retains an embedded NUL that ZipInfo.filename truncates.
                name = safe_path(info.orig_filename, directory=info.is_dir())
                folded = name.casefold()
                if folded in seen:
                    raise RecoveryError("ZIP มีชื่อซ้ำหรือชนกันเมื่อไม่แยกตัวพิมพ์")
                seen.add(folded)
                if name != spec.package_root and not name.startswith(spec.package_root + "/"):
                    raise RecoveryError("ZIP มีข้อมูลนอกรากแพ็กที่กำหนด")
                mode = info.external_attr >> 16
                filetype = stat.S_IFMT(mode)
                if filetype not in (0, stat.S_IFREG, stat.S_IFDIR) or stat.S_ISLNK(mode):
                    raise RecoveryError("ไม่รับ symlink หรือ special file ใน ZIP")
                if info.flag_bits & 1:
                    raise RecoveryError("ไม่รับ ZIP เข้ารหัส")
                if info.file_size > MAX_MEMBER:
                    raise RecoveryError("สมาชิก ZIP ใหญ่เกิน 2 MiB ของขอบเขตส่งซอร์ส")
                if info.is_dir():
                    directories.add(folded)
                else:
                    files.add(folded)
                entries.append((info, name))
            for name in seen:
                parents = list(PurePosixPath(name).parents)[:-1]
                if any(str(parent) in files for parent in parents):
                    raise RecoveryError("ZIP มีพาธไฟล์ชนกับโฟลเดอร์")
            for info, name in entries:
                if info.is_dir():
                    continue
                if name == spec.package_root:
                    raise RecoveryError("รากแพ็กต้องเป็นโฟลเดอร์")
                relative = name[len(spec.package_root) + 1:]
                include, reason = source_selection(relative)
                if not include:
                    omitted.append({"path": relative, "reason": reason})
                    continue
                if total + info.file_size > MAX_TEXT:
                    raise RecoveryError("ซอร์สรวมเกินขอบเขต 24 MiB")
                with archive.open(info) as source:
                    raw = source.read(MAX_MEMBER + 1)
                if len(raw) != info.file_size or len(raw) > MAX_MEMBER:
                    raise RecoveryError("ขนาดเนื้อหา ZIP ไม่ตรง metadata")
                try:
                    text = raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise RecoveryError("ไฟล์ซอร์สไม่ใช่ UTF-8 ที่ถูกต้อง") from exc
                if "\0" in text or any(ord(c) < 32 and c not in "\t\r\n" for c in text):
                    raise RecoveryError("ไฟล์ที่อ้างเป็นข้อความมี NUL/control bytes")
                total += len(raw)
                records.append({"path": relative, "size_bytes": len(raw), "sha256": digest(raw), "content": text})
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError) as exc:
        raise RecoveryError("อ่านโครงสร้างหรือ CRC ของ ZIP ไม่ผ่าน") from exc
    required = {APP_PREFIX + "app/server.py", APP_PREFIX + "app/static/index.html"}
    if not required.issubset({r["path"] for r in records}):
        raise RecoveryError("ไม่พบ server.py และ static/index.html ของแอปในแพ็ก")
    records.sort(key=lambda r: r["path"])
    index = [{k: r[k] for k in ("path", "size_bytes", "sha256")} for r in records]
    meta = {"format": "ContinueRetro source handoff v1", "release_version": spec.version,
            "archive_sha256": digest(blob), "archive_size_bytes": len(blob),
            "package_root": spec.package_root, "file_count": len(records), "text_bytes": total,
            "source_index_sha256": digest(_json(index)), "source_only": True,
            "archive_code_executed": False, "uploaded": False,
            "runnable_app_export": False}
    return {**meta, "files": index, "omitted": sorted(omitted, key=lambda r: r["path"])}, records


def render_bundle(index: dict, records: list[dict]) -> bytes:
    """Byte lengths delimit content; source containing our marker cannot escape."""
    meta = {k: v for k, v in index.items() if k not in {"files", "omitted"}}
    out = io.BytesIO()
    out.write(MAGIC + _json(meta) + b"\n")
    for row in records:
        raw = row["content"].encode("utf-8")
        header = {k: row[k] for k in ("path", "size_bytes", "sha256")}
        if digest(raw) != header["sha256"] or len(raw) != header["size_bytes"]:
            raise RecoveryError("เนื้อหาซอร์สเปลี่ยนก่อนสร้าง bundle")
        out.write(b"@@FILE " + _json(header) + b"\n" + raw + b"\n@@END\n")
    out.write(b"@@COMPLETE\n")
    return out.getvalue()


def parse_bundle(blob: bytes) -> tuple[dict, list[dict]]:
    """Verify transfer integrity; does NOT authenticate the sender or execute code."""
    if not isinstance(blob, bytes) or len(blob) > MAX_TEXT + 4 * 1024 * 1024:
        raise RecoveryError("bundle ไม่ใช่ bytes หรือใหญ่เกินกำหนด")
    stream = io.BytesIO(blob)
    if stream.readline(len(MAGIC) + 1) != MAGIC:
        raise RecoveryError("ไม่ใช่ source bundle v1")
    def read_object(prefix=b""):
        line = stream.readline(MAX_HEADER + 1)
        if len(line) > MAX_HEADER or not line.endswith(b"\n") or not line.startswith(prefix):
            raise RecoveryError("header ขาดหายหรือยาวเกินขอบเขต")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise RecoveryError("JSON header มี key ซ้ำ")
                result[key] = value
            return result
        try:
            value = json.loads(line[len(prefix):].decode("utf-8"), object_pairs_hook=unique)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise RecoveryError("header ไม่ใช่ JSON UTF-8 ที่ถูกต้อง") from exc
        if not isinstance(value, dict):
            raise RecoveryError("header ต้องเป็น object")
        return value
    meta = read_object()
    count = meta.get("file_count")
    if type(count) is not int or not 1 <= count <= MAX_MEMBERS:
        raise RecoveryError("จำนวนไฟล์ไม่ถูกต้อง")
    if meta.get("format") != "ContinueRetro source handoff v1" or meta.get("source_only") is not True:
        raise RecoveryError("bundle format/scope ไม่ตรง")
    rows, seen, total = [], set(), 0
    for _ in range(count):
        header = read_object(b"@@FILE ")
        if set(header) != {"path", "size_bytes", "sha256"}:
            raise RecoveryError("ฟิลด์ file header ไม่ตรง")
        path = safe_path(header["path"])
        if path.casefold() in seen or not source_selection(path)[0]:
            raise RecoveryError("bundle มีไฟล์ซ้ำหรือข้อมูลนอก source allowlist")
        seen.add(path.casefold())
        size = header["size_bytes"]
        if type(size) is not int or not 0 <= size <= MAX_MEMBER or total + size > MAX_TEXT:
            raise RecoveryError("ขนาดไฟล์ใน bundle ไม่ถูกต้อง")
        raw = stream.read(size)
        if len(raw) != size or digest(raw) != header["sha256"] or stream.read(7) != b"\n@@END\n":
            raise RecoveryError("เนื้อหา bundle ขาดหายหรือ checksum ไม่ตรง")
        try:
            content = raw.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise RecoveryError("เนื้อหาไม่ใช่ UTF-8") from exc
        if "\0" in content or any(ord(c) < 32 and c not in "\t\r\n" for c in content):
            raise RecoveryError("พบ control bytes ใน source bundle")
        rows.append({**header, "content": content})
        total += size
    if stream.read() != b"@@COMPLETE\n":
        raise RecoveryError("bundle ยังไม่จบหรือมีข้อมูลต่อท้าย")
    ordered = sorted(rows, key=lambda r: r["path"])
    expected = digest(_json([{k: r[k] for k in ("path", "size_bytes", "sha256")} for r in ordered]))
    if expected != meta.get("source_index_sha256") or total != meta.get("text_bytes"):
        raise RecoveryError("source index ไม่ตรงเนื้อหาที่อ่าน")
    return meta, rows


def prepare(archive_path: Path, output_parent: Path | None = None,
            *, spec: ReleaseSpec = BASELINE) -> dict:
    """Read exactly one selected ZIP; create a new handoff directory atomically."""
    source = Path(archive_path).expanduser()
    if not source.is_file() or source.suffix.casefold() != ".zip":
        raise RecoveryError("เลือกไฟล์ ZIP v0.6.0 ที่มีอยู่จริง")
    if source.stat().st_size > MAX_ARCHIVE:
        raise RecoveryError("ZIP ใหญ่เกิน 16 MiB — ไม่รับ ROM หรือแพ็กอื่น")
    with source.open("rb") as fh:
        blob = fh.read(MAX_ARCHIVE + 1)
    index, records = inspect_release_bytes(blob, spec)
    bundle = render_bundle(index, records)
    parse_bundle(bundle)  # Independent framed-text transfer check before writing.
    index_bytes = json.dumps(index, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    sums = f"{digest(bundle)}  {BUNDLE_NAME}\n{digest(index_bytes)}  {INDEX_NAME}\n".encode("ascii")
    outputs = {BUNDLE_NAME: bundle, INDEX_NAME: index_bytes, SUMS_NAME: sums}
    parent = Path(output_parent).expanduser() if output_parent else source.parent
    if not parent.is_dir():
        raise RecoveryError("โฟลเดอร์ปลายทางไม่อยู่แล้ว ไม่สร้างพาธแทนไดรฟ์ที่หาย")
    parent = parent.resolve(strict=True)
    final = parent / f"ContinueRetro_Source_Handoff_v{spec.version}_{spec.archive_sha256[:12]}"
    if final.exists() or final.is_symlink():
        if final.is_symlink() or not final.is_dir() or {p.name for p in final.iterdir()} != set(outputs):
            raise RecoveryError("ปลายทางมีข้อมูลอื่นอยู่แล้ว — ไม่เขียนทับ")
        for name, data in outputs.items():
            existing = final / name
            if existing.is_symlink() or not existing.is_file() or existing.stat().st_size != len(data) or existing.read_bytes() != data:
                raise RecoveryError("ผลลัพธ์เดิมต่างกัน — ไม่เขียนทับหรือแก้ไฟล์เดิม")
        return {"directory": str(final), "bundle": str(final / BUNDLE_NAME), "reused": True, "file_count": len(records)}
    temporary = Path(tempfile.mkdtemp(prefix=".continue-retro-source-", dir=parent))
    try:
        for name, data in outputs.items():
            with (temporary / name).open("xb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        # A same-parent rename retains previous source files and avoids partial output.
        if final.exists() or final.is_symlink():
            raise RecoveryError("มีผู้สร้างผลลัพธ์ชื่อเดียวกันระหว่างทำงาน — ไม่เขียนทับ")
        temporary.rename(final)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"directory": str(final), "bundle": str(final / BUNDLE_NAME), "reused": False, "file_count": len(records)}


def choose_archive() -> Path | None:
    if sys.platform == "darwin":
        result = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose file with prompt "เลือก ContinueRetro_Studio_ExternalDrive_v0.6.0.zip เดิม (ไม่ใช่ ZIP เกม)" of type {"zip"})'],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return Path(result.stdout.strip())
    value = input("พาธ ContinueRetro_Studio_ExternalDrive_v0.6.0.zip (Enter เพื่อยกเลิก): ").strip()
    return Path(value.strip('"')) if value else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="เตรียมซอร์ส v0.6.0 เป็น TXT ที่อ่านต่อได้ ไม่ใช่ตัวอัปเดต")
    parser.add_argument("--zip", type=Path, help="ZIP ตัวแอป v0.6.0 เดิม ไม่ใช่ ZIP โปรเจกต์/เกม")
    parser.add_argument("--output-parent", type=Path, help="โฟลเดอร์ที่มีอยู่แล้ว; ค่าเริ่มต้นอยู่ข้าง ZIP")
    args = parser.parse_args(argv)
    try:
        source = args.zip or choose_archive()
        if source is None:
            print("ยกเลิก — ไม่มีไฟล์ที่ถูกแก้")
            return 0
        print("อ่านและตรวจแฮชแพ็กเดิม — ไม่อ่านโฟลเดอร์ PRIVATE ของการติดตั้ง")
        result = prepare(source, args.output_parent)
        print(f"เตรียมซอร์ส {result['file_count']} ไฟล์แล้ว (ใช้ผลเดิม: {result['reused']})")
        print("แนบไฟล์นี้กลับในแชทเพื่อให้ตรวจโค้ดและเชื่อมงานต่อได้:")
        print(result["bundle"])
        print("ไม่มีการอัปโหลด ติดตั้ง รันโค้ดในแพ็ก หรือเปลี่ยนไฟล์เกม/ฟอนต์/ฐานข้อมูล")
        return 0
    except KeyboardInterrupt:
        print("หยุดโดยผู้ใช้ — ไม่เปลี่ยนแพ็กต้นฉบับ", file=sys.stderr)
        return 130
    except (RecoveryError, OSError) as exc:
        print(f"ยังไม่ส่งออก: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
