#!/usr/bin/env bash
# Shared path/hash helpers. Caller chooses strict-shell options.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$PROJECT_ROOT/tools"
CACHE="$TOOLS/cache"
INSTALLED="$TOOLS/installed"
BIN="$TOOLS/bin"
export PATH="$BIN:$PATH"
sha256_cmd() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$@"
  else python3 - "$@" <<'PYHASH_7821'
import hashlib,sys
for p in sys.argv[1:]:
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    print(h.hexdigest(),p)
PYHASH_7821
  fi
}
os_id(){ uname -s | tr '[:upper:]' '[:lower:]'; }
arch_id(){ case "$(uname -m)" in x86_64|amd64) echo x86_64;; arm64|aarch64) echo aarch64;; *) uname -m;; esac; }
