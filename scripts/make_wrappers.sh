#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
mkdir -p "$BIN"
if [ -x "$INSTALLED/cmake-4.4.3/bin/cmake" ]; then
  ln -sfn ../installed/cmake-4.4.3/bin/cmake "$BIN/cmake"
  ln -sfn ../installed/cmake-4.4.3/bin/ctest "$BIN/ctest"
  ln -sfn ../installed/cmake-4.4.3/bin/cpack "$BIN/cpack"
fi
[ ! -x "$INSTALLED/ninja-1.13.2/ninja" ] || ln -sfn ../installed/ninja-1.13.2/ninja "$BIN/ninja"
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
R="$(cd "$(dirname "$0")/../.." && pwd)"; L="$R/tools/installed/llvm-17.0.6"; C="$L/bin/clang"; RES="$L/lib/clang/17"
G="$R/tools/installed/gcc-mipsel-none-elf-12.3.0/bin/mipsel-none-elf-gcc"
if [ -x "$C" ] && [ -d "$RES/include" ] && [ "$(wc -c < "$C")" -eq 188753776 ] && "$C" --version >/dev/null 2>&1; then
  exec "$C" -resource-dir "$RES" --target=mipsel-none-elf -march=mips1 -mabi=32 -msoft-float -mno-abicalls -ffreestanding -fno-pic -G0 "$@"
fi
[ -x "$G" ] || { echo 'portable PS1 MIPS compiler missing; restore LLVM 17.0.6 or GCC 12.3.0' >&2; exit 127; }
exec "$G" -march=r3000 -mabi=32 -msoft-float -mno-abicalls -ffreestanding -fno-pic -G0 "$@"
WM1
cat > "$BIN/ps1-mips-as" <<'WM2'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; C="$R/tools/installed/llvm-17.0.6/bin/clang"
G="$R/tools/installed/gcc-mipsel-none-elf-12.3.0/bin/mipsel-none-elf-gcc"
if [ -x "$C" ] && [ "$(wc -c < "$C")" -eq 188753776 ] && "$C" --version >/dev/null 2>&1; then
  exec "$C" --target=mipsel-none-elf -march=mips1 -mabi=32 -msoft-float -mno-abicalls -fno-pic -G0 -x assembler -c "$@"
fi
[ -x "$G" ] || { echo 'portable PS1 MIPS assembler missing' >&2; exit 127; }
exec "$G" -march=r3000 -mabi=32 -msoft-float -mno-abicalls -fno-pic -G0 -x assembler -c "$@"
WM2
cat > "$BIN/ps1-mips-ld" <<'WM3'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; C="$R/tools/installed/llvm-17.0.6/bin/clang"; L="$R/tools/installed/llvm-17.0.6/bin/ld.lld"
G="$R/tools/installed/gcc-mipsel-none-elf-12.3.0/bin/mipsel-none-elf-ld"
if [ -x "$C" ] && [ "$(wc -c < "$C")" -eq 188753776 ] && "$C" --version >/dev/null 2>&1; then exec "$L" -m elf32ltsmip "$@"; fi
[ -x "$G" ] || { echo 'portable PS1 MIPS linker missing' >&2; exit 127; }
exec "$G" -m elf32elmip "$@"
WM3
cat > "$BIN/ps1-mips-objcopy" <<'WM4'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; C="$R/tools/installed/llvm-17.0.6/bin/clang"; O="$R/tools/installed/llvm-17.0.6/bin/llvm-objcopy"
G="$R/tools/installed/gcc-mipsel-none-elf-12.3.0/bin/mipsel-none-elf-objcopy"
if [ -x "$C" ] && [ "$(wc -c < "$C")" -eq 188753776 ] && "$C" --version >/dev/null 2>&1; then exec "$O" "$@"; fi
[ -x "$G" ] || { echo 'portable PS1 MIPS objcopy missing' >&2; exit 127; }
exec "$G" "$@"
WM4
cat > "$BIN/ps1-mips-objdump" <<'WM5'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; C="$R/tools/installed/llvm-17.0.6/bin/clang"; O="$R/tools/installed/llvm-17.0.6/bin/llvm-objdump"
G="$R/tools/installed/gcc-mipsel-none-elf-12.3.0/bin/mipsel-none-elf-objdump"
if [ -x "$C" ] && [ "$(wc -c < "$C")" -eq 188753776 ] && "$C" --version >/dev/null 2>&1; then exec "$O" "$@"; fi
[ -x "$G" ] || { echo 'portable PS1 MIPS objdump missing' >&2; exit 127; }
exec "$G" "$@"
WM5
cat > "$BIN/xdelta3" <<'W7'
#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/../.." && pwd)"; X="$R/tools/installed/xdelta3/xdelta3"
[ -x "$X" ] || { echo 'xdelta3 missing; restore the recovery artifact or run bootstrap on a networked machine' >&2; exit 127; }; exec "$X" "$@"
W7
chmod +x "$BIN"/mkpsxiso "$BIN"/dumpsxiso "$BIN"/jpsxdec "$BIN"/ghidra-headless "$BIN"/duckstation "$BIN"/pcsx-redux "$BIN"/xdelta3 "$BIN"/ps1-mips-cc "$BIN"/ps1-mips-as "$BIN"/ps1-mips-ld "$BIN"/ps1-mips-objcopy "$BIN"/ps1-mips-objdump
