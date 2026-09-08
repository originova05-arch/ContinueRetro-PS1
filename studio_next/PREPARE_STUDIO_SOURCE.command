#!/bin/bash
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
trap 'printf "\nกด Enter เพื่อปิดหน้าต่างนี้…"; read -r _' EXIT
printf '\nContinueRetro — เตรียมซอร์ส v0.6.0 เพื่อรับงานต่อ\n'
printf 'ไม่ใช่ตัวอัปเดต ไม่แก้แอป ไม่อ่าน ROM/ฟอนต์/ฐานข้อมูล และไม่อัปโหลดเอง\n\n'
if ! command -v python3 >/dev/null 2>&1; then
  printf 'ไม่พบ Python 3 กรุณาใช้ Python ที่ใช้เปิด Studio เดิม\n'
  exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  printf 'ต้องใช้ Python 3.10 ขึ้นไป\n'
  exit 1
fi
python3 "$HERE/source_bridge.py" "$@"
