#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
"$PROJECT_ROOT/scripts/make_wrappers.sh" >/dev/null
T="$PROJECT_ROOT/tools/tests"; B="$PROJECT_ROOT/tools/build/mips-smoke"; mkdir -p "$B"
"$BIN/ps1-mips-cc" -c "$T/mips_smoke.c" -o "$B/mips_smoke.o"
"$BIN/ps1-mips-ld" -Ttext=0x80010000 -e cr_ps1_add "$B/mips_smoke.o" -o "$B/mips_smoke.elf"
"$BIN/ps1-mips-objcopy" -j .text -O binary "$B/mips_smoke.elf" "$B/mips_smoke.text.bin"
file "$B/mips_smoke.o" | grep -q 'MIPS'
"$BIN/ps1-mips-objdump" -d "$B/mips_smoke.elf" > "$B/mips_smoke.disasm.txt"
grep -q 'cr_ps1_add' "$B/mips_smoke.disasm.txt"
echo "OK: PS1 MIPS-I compile/link/objcopy smoke test ($(wc -c < "$B/mips_smoke.text.bin") byte .text)"
