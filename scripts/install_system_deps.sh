#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
[ "${CR_SKIP_SYSTEM_DEPS:-0}" = 1 ] && { echo 'Skipping system dependencies (CR_SKIP_SYSTEM_DEPS=1).'; exit 0; }
have(){ command -v "$1" >/dev/null 2>&1; }
need=()
for c in bash python3 git cmake ninja java unzip ffmpeg clang ld.lld llvm-objcopy llvm-objdump; do have "$c" || need+=("$c"); done
if ! have magick && ! have convert; then need+=(imagemagick); fi
[ ${#need[@]} -eq 0 ] && { echo 'System dependencies already present.'; exit 0; }
echo "Missing system dependencies: ${need[*]}"
run_priv(){ if [ "$(id -u)" -eq 0 ]; then "$@"; elif have sudo; then sudo "$@"; else echo 'No root/sudo available for package installation.' >&2; return 1; fi; }
OS="$(os_id)"
case "$OS" in
  linux)
    if have apt-get; then
      echo 'Installing Debian/Ubuntu packages...'
      run_priv apt-get update || { echo 'WARN: apt-get update failed; continuing so doctor can report missing dependencies.' >&2; exit 0; }
      run_priv apt-get install -y git cmake ninja-build unzip openjdk-21-jre-headless python3 curl ffmpeg imagemagick clang lld build-essential || true
    elif have pacman; then
      echo 'Installing Arch packages...'
      run_priv pacman -S --needed --noconfirm git cmake ninja unzip jre-openjdk python curl ffmpeg imagemagick clang lld base-devel || true
    else
      echo 'WARN: unsupported Linux package manager; install the listed dependencies manually.' >&2
    fi
    ;;
  darwin)
    if have brew; then
      brew install git cmake ninja openjdk@21 python curl ffmpeg imagemagick llvm || true
    else
      echo 'WARN: Homebrew is required for automatic macOS dependency setup.' >&2
    fi
    ;;
  *) echo "WARN: unsupported OS $OS; install dependencies manually." >&2 ;;
esac
