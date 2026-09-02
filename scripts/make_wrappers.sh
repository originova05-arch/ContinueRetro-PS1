#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
mkdir -p "$BIN"
cat > "$BIN/mkpsxiso" <<'W1'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"
for p in "$R/tools/installed/mkpsxiso"/*/bin/mkpsxiso; do [ -x "$p" ] && exec "$p" "$@"; done
echo 'mkpsxiso missing; run ./scripts/bootstrap.sh' >&2; exit 127
W1
cat > "$BIN/dumpsxiso" <<'W2'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"
for p in "$R/tools/installed/mkpsxiso"/*/bin/dumpsxiso; do [ -x "$p" ] && exec "$p" "$@"; done
echo 'dumpsxiso missing; run ./scripts/bootstrap.sh' >&2; exit 127
W2
cat > "$BIN/jpsxdec" <<'W3'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; J="$R/tools/installed/jpsxdec/jpsxdec_v2.1-beta/jpsxdec.jar"
[ -f "$J" ] || { echo 'jPSXdec missing' >&2; exit 127; }; exec java -jar "$J" "$@"
W3
cat > "$BIN/ghidra-headless" <<'W4'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; G="$R/tools/installed/ghidra/ghidra_12.1.3_PUBLIC/support/analyzeHeadless"
[ -x "$G" ] || { echo 'Ghidra missing' >&2; exit 127; }; exec "$G" "$@"
W4
cat > "$BIN/duckstation" <<'W5'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; A="$R/tools/installed/duckstation/squashfs-root/AppRun"
[ -x "$A" ] || { echo 'DuckStation missing/extraction incomplete' >&2; exit 127; }; exec "$A" "$@"
W5
cat > "$BIN/pcsx-redux" <<'W6'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; A="$R/tools/installed/pcsx-redux/squashfs-root/AppRun"
[ -x "$A" ] || { echo 'PCSX-Redux missing/extraction incomplete' >&2; exit 127; }; exec "$A" "$@"
W6
cat > "$BIN/ps1-mips-cc" <<'WM1'
#!/usr/bin/env bash
set -euo pipefail
C="$(command -v clang || true)"; [ -n "$C" ] || { echo 'clang missing; run ./scripts/bootstrap.sh' >&2; exit 127; }
exec "$C" --target=mipsel-none-elf -march=mips1 -mabi=32 -msoft-float -mno-abicalls -ffreestanding -fno-pic -G0 "$@"
WM1
cat > "$BIN/ps1-mips-as" <<'WM2'
#!/usr/bin/env bash
set -euo pipefail
C="$(command -v clang || true)"; [ -n "$C" ] || { echo 'clang missing' >&2; exit 127; }
exec "$C" --target=mipsel-none-elf -march=mips1 -mabi=32 -msoft-float -mno-abicalls -fno-pic -G0 -x assembler -c "$@"
WM2
cat > "$BIN/ps1-mips-ld" <<'WM3'
#!/usr/bin/env bash
set -euo pipefail
L="$(command -v ld.lld || true)"; [ -n "$L" ] || { echo 'ld.lld missing' >&2; exit 127; }
exec "$L" -m elf32ltsmip "$@"
WM3
cat > "$BIN/ps1-mips-objcopy" <<'WM4'
#!/usr/bin/env bash
set -euo pipefail
O="$(command -v llvm-objcopy || true)"; [ -n "$O" ] || { echo 'llvm-objcopy missing' >&2; exit 127; }
exec "$O" "$@"
WM4
cat > "$BIN/ps1-mips-objdump" <<'WM5'
#!/usr/bin/env bash
set -euo pipefail
O="$(command -v llvm-objdump || true)"; [ -n "$O" ] || { echo 'llvm-objdump missing' >&2; exit 127; }
exec "$O" "$@"
WM5
cat > "$BIN/xdelta3" <<'W7'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; X="$R/tools/installed/xdelta3/xdelta3"
[ -x "$X" ] || { echo 'xdelta3 missing; run bootstrap on a networked machine or provide/build it' >&2; exit 127; }; exec "$X" "$@"
W7
chmod +x "$BIN"/mkpsxiso "$BIN"/dumpsxiso "$BIN"/jpsxdec "$BIN"/ghidra-headless "$BIN"/duckstation "$BIN"/pcsx-redux "$BIN"/xdelta3 "$BIN"/ps1-mips-cc "$BIN"/ps1-mips-as "$BIN"/ps1-mips-ld "$BIN"/ps1-mips-objcopy "$BIN"/ps1-mips-objdump
