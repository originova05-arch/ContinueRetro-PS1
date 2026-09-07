#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

resolve_retrothai() {
  if [ -n "${RETROTHAI_BIN:-}" ] && [ -x "$RETROTHAI_BIN" ]; then
    printf '%s\n' "$RETROTHAI_BIN"
    return 0
  fi
  if command -v retrothai >/dev/null 2>&1; then
    command -v retrothai
    return 0
  fi
  for candidate in \
    "$HOME/.local/bin/retrothai" \
    "$ROOT/.agents/skills/ps1-thai-game-localizer/retrothai" \
    "$HOME/.agents/skills/ps1-thai-game-localizer/retrothai" \
    "$HOME/.codex/skills/ps1-thai-game-localizer/retrothai"
  do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! RETROTHAI="$(resolve_retrothai)"; then
  cat >&2 <<'EOF'
ERROR: ps1-thai-game-localizer v4.1+ is not installed or its launcher cannot be found.
Install the verified skill bundle, then rerun this command.
Expected launcher: ~/.local/bin/retrothai
EOF
  exit 2
fi

case "${1:-}" in
  run)
    shift
    exec "$RETROTHAI" guard --repo "$ROOT" "$@"
    ;;
  status)
    shift
    exec "$RETROTHAI" status --repo "$ROOT" "$@"
    ;;
  record-error)
    shift
    exec "$RETROTHAI" record-error --repo "$ROOT" "$@"
    ;;
  recover)
    shift
    exec "$RETROTHAI" recover --repo "$ROOT" "$@"
    ;;
  *)
    exec "$RETROTHAI" recover --repo "$ROOT" "$@"
    ;;
esac
