#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
mkdir -p "$CACHE" "$INSTALLED" "$BIN" "$TOOLS/src"
OS="$(os_id)"; ARCH="$(arch_id)"
echo "ContinueRetro-PS1 bootstrap: $OS/$ARCH"
"$PROJECT_ROOT/scripts/install_system_deps.sh" || true
have(){ command -v "$1" >/dev/null 2>&1; }
download(){
  local url="$1" out="$2"; echo "Downloading $(basename "$out")"
  if have curl; then curl -L --fail --retry 3 -o "$out.part" "$url" && mv "$out.part" "$out"; return; fi
  if have wget; then wget -O "$out.part" "$url" && mv "$out.part" "$out"; return; fi
  python3 - "$url" "$out" <<'PYDL_7821'
import os,sys,urllib.request
u,o=sys.argv[1:]; t=o+'.part'; urllib.request.urlretrieve(u,t); os.replace(t,o)
PYDL_7821
}
verify_hash(){ local f="$1" expected="$2" got; [ -f "$f" ] || return 1; got="$(sha256_cmd "$f"|awk '{print $1}')"; [ "$expected" = TO_BE_RECORDED ] || [ "$expected" = NOT_BUILT_YET ] || [ "$got" = "$expected" ] || { echo "HASH MISMATCH: $f" >&2; echo "expected=$expected" >&2; echo "got=$got" >&2; return 1; }; }
ensure_archive(){ local fn="$1" sha="$2" url="$3" f="$CACHE/$1"; if verify_hash "$f" "$sha"; then return 0; fi; [ "$url" != CACHE_OR_BUILD_FROM_SOURCE ] && [ "$url" != USER_PROJECT_ASSET ] || return 1; rm -f "$f"; download "$url" "$f"; verify_hash "$f" "$sha"; }

if [ ! -x "$INSTALLED/ghidra/ghidra_12.1.3_PUBLIC/support/analyzeHeadless" ]; then
  ensure_archive ghidra_12.1.3_PUBLIC_20260817.zip 93a5d11a9ad510622acaaf908c556a7b9b764d338e78a7567f3689bf5081fd54 https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.3_build/ghidra_12.1.3_PUBLIC_20260817.zip
  rm -rf "$INSTALLED/ghidra"; mkdir -p "$INSTALLED/ghidra"; unzip -q "$CACHE/ghidra_12.1.3_PUBLIC_20260817.zip" -d "$INSTALLED/ghidra"
fi

if [ "$OS" = linux ] && [ "$ARCH" = x86_64 ]; then
  if [ ! -x "$INSTALLED/mkpsxiso/mkpsxiso-2.30-Linux/bin/mkpsxiso" ]; then
    ensure_archive mkpsxiso-2.30-Linux.zip 8e387e6db51dee3eb7cb08f4d59293a24c48f58bd541631acf9301d78015a1fc https://github.com/Lameguy64/mkpsxiso/releases/download/v2.30/mkpsxiso-2.30-Linux.zip
    rm -rf "$INSTALLED/mkpsxiso"; mkdir -p "$INSTALLED/mkpsxiso"; unzip -q "$CACHE/mkpsxiso-2.30-Linux.zip" -d "$INSTALLED/mkpsxiso"
  fi
elif [ "$OS" = darwin ]; then
  if [ ! -x "$INSTALLED/mkpsxiso/mkpsxiso-2.30-Darwin/bin/mkpsxiso" ]; then
    [ -f "$CACHE/mkpsxiso-2.30-Darwin.zip" ] || download https://github.com/Lameguy64/mkpsxiso/releases/download/v2.30/mkpsxiso-2.30-Darwin.zip "$CACHE/mkpsxiso-2.30-Darwin.zip"
    rm -rf "$INSTALLED/mkpsxiso"; mkdir -p "$INSTALLED/mkpsxiso"; unzip -q "$CACHE/mkpsxiso-2.30-Darwin.zip" -d "$INSTALLED/mkpsxiso"
  fi
fi

if [ ! -f "$INSTALLED/jpsxdec/jpsxdec_v2.1-beta/jpsxdec.jar" ]; then
  ensure_archive jpsxdec_v2.1-beta.zip e11787a2e05b6a4b6ee07972439e50da9e6798f0ca505e748f4969b3d91cd45b https://github.com/m35/jpsxdec/releases/download/v2.1/jpsxdec_v2.1-beta.zip
  rm -rf "$INSTALLED/jpsxdec"; mkdir -p "$INSTALLED/jpsxdec"; unzip -q "$CACHE/jpsxdec_v2.1-beta.zip" -d "$INSTALLED/jpsxdec"
fi

if [ -f "$CACHE/Continue_Retro_Thai_Game_FontKit_v1.2.1.zip" ] && [ ! -d "$INSTALLED/fontkit/Continue_Retro_Thai_Game_FontKit" ]; then mkdir -p "$INSTALLED/fontkit"; unzip -q "$CACHE/Continue_Retro_Thai_Game_FontKit_v1.2.1.zip" -d "$INSTALLED/fontkit"; fi

if [ "$OS" = linux ] && [ "$ARCH" = x86_64 ]; then
  if [ -f "$CACHE/DuckStation-x64.AppImage" ]; then
    verify_hash "$CACHE/DuckStation-x64.AppImage" c5c8a9de4dfc10e794137dcb8bab9760ca578df2aa7be8c1215171bebbba5965
  else
    echo 'DuckStation exact cache absent; trying rolling URL and enforcing locked hash.'
    ensure_archive DuckStation-x64.AppImage c5c8a9de4dfc10e794137dcb8bab9760ca578df2aa7be8c1215171bebbba5965 https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage
  fi
  mkdir -p "$INSTALLED/duckstation"; cp -f "$CACHE/DuckStation-x64.AppImage" "$INSTALLED/duckstation/DuckStation-x64.AppImage"; chmod +x "$INSTALLED/duckstation/DuckStation-x64.AppImage"
  if [ ! -x "$INSTALLED/duckstation/squashfs-root/AppRun" ]; then rm -rf "$INSTALLED/duckstation/squashfs-root"; (cd "$INSTALLED/duckstation" && ./DuckStation-x64.AppImage --appimage-extract >/dev/null); fi

  if [ -f "$CACHE/PCSX-Redux-2a36099dc-anylinux-x86_64.AppImage" ]; then
    verify_hash "$CACHE/PCSX-Redux-2a36099dc-anylinux-x86_64.AppImage" 92e000c82813f7a0123d2268e04811515dba4b04169d1616bec62547b7eb7f0e
    mkdir -p "$INSTALLED/pcsx-redux"; cp -f "$CACHE/PCSX-Redux-2a36099dc-anylinux-x86_64.AppImage" "$INSTALLED/pcsx-redux/PCSX-Redux.AppImage"; chmod +x "$INSTALLED/pcsx-redux/PCSX-Redux.AppImage"
    if [ ! -x "$INSTALLED/pcsx-redux/squashfs-root/AppRun" ]; then rm -rf "$INSTALLED/pcsx-redux/squashfs-root"; (cd "$INSTALLED/pcsx-redux" && ./PCSX-Redux.AppImage --appimage-extract >/dev/null); fi
  else echo 'WARN: exact PCSX-Redux AppImage cache missing; build pinned source on this host.' >&2; fi
fi

if [ ! -x "$INSTALLED/xdelta3/xdelta3" ]; then
  mkdir -p "$INSTALLED/xdelta3"
  if [ "$OS" = linux ] && [ "$ARCH" = x86_64 ]; then
    XDARC="$CACHE/xdelta3-3.2.0-linux-x86_64.tar.gz"
    if verify_hash "$XDARC" 480295c7a41fea6503659f19ddc61676c0df4834e2292846ba97de30c68c2397 || ensure_archive xdelta3-3.2.0-linux-x86_64.tar.gz 480295c7a41fea6503659f19ddc61676c0df4834e2292846ba97de30c68c2397 https://github.com/jmacd/xdelta/releases/download/v3.2.0/xdelta3-3.2.0-linux-x86_64.tar.gz; then
      rm -rf "$INSTALLED/xdelta3/unpack"; mkdir -p "$INSTALLED/xdelta3/unpack"
      tar -xzf "$XDARC" -C "$INSTALLED/xdelta3/unpack"
      FOUND="$(find "$INSTALLED/xdelta3/unpack" -type f -name xdelta3 -perm -111 | head -1 || true)"
      [ -n "$FOUND" ] && cp "$FOUND" "$INSTALLED/xdelta3/xdelta3"
    fi
  fi
  SYS_XD="$(command -v xdelta3 2>/dev/null || true)"
  if [ ! -x "$INSTALLED/xdelta3/xdelta3" ] && [ -n "$SYS_XD" ] && [ "$(cd "$(dirname "$SYS_XD")" && pwd)/$(basename "$SYS_XD")" != "$BIN/xdelta3" ]; then
    if "$SYS_XD" -V >/dev/null 2>&1; then cp "$SYS_XD" "$INSTALLED/xdelta3/xdelta3"; fi
  fi
  if [ ! -x "$INSTALLED/xdelta3/xdelta3" ] && have git && have cmake; then
    XD="$TOOLS/src/xdelta"
    if [ ! -d "$XD/.git" ]; then git clone https://github.com/jmacd/xdelta.git "$XD" || rm -rf "$XD"; fi
    if [ -d "$XD/.git" ]; then
      git -C "$XD" fetch --all --tags || true; git -C "$XD" checkout ff322e592383227b0d65ddfde7e0e5bbc504dc15
      cmake -S "$XD/xdelta3" -B "$XD/build" -DCMAKE_BUILD_TYPE=Release -DXD3_LZMA_MODE=off -DXD3_ARMOR=OFF -DXD3_BUILD_TESTS=OFF
      cmake --build "$XD/build" -j "${CR_JOBS:-2}"; cp "$XD/build/xdelta3" "$INSTALLED/xdelta3/xdelta3"
    else echo 'WARN: xdelta3 archive/source unavailable; doctor will report missing.' >&2; fi
  fi
fi
if [ "${CR_FETCH_SOURCES:-0}" = 1 ]; then
  clone_pin(){ local n="$1" u="$2" ref="$3" d="$TOOLS/src/$1"; [ -d "$d/.git" ] || git clone --recursive "$u" "$d"; git -C "$d" fetch --all --tags; git -C "$d" checkout "$ref"; git -C "$d" submodule update --init --recursive; }
  clone_pin ghidra https://github.com/NationalSecurityAgency/ghidra.git Ghidra_12.1.3_build || true
  clone_pin mkpsxiso https://github.com/Lameguy64/mkpsxiso.git v2.30 || true
  clone_pin duckstation https://github.com/stenzek/duckstation.git fe2306b1f0f7dd64cbc9aa8eb12269715ba799b5 || true
  clone_pin pcsx-redux https://github.com/grumpycoders/pcsx-redux.git 2a36099dc24c5a746854e3de8359c40e5af21c10 || true
  clone_pin xdelta https://github.com/jmacd/xdelta.git ff322e592383227b0d65ddfde7e0e5bbc504dc15 || true
fi

"$PROJECT_ROOT/scripts/make_wrappers.sh"
"$PROJECT_ROOT/scripts/verify_toolchain.sh" || true
echo 'Bootstrap completed. Run: ./scripts/doctor.sh'
