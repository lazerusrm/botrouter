#!/usr/bin/env bash
# Fail-closed BotRouter host hook. Safe after a host bundle upgrade; no restart.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/../xai-prompt-session.cjs" ]]; then
  ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [[ -f "$SCRIPT_DIR/xai-prompt-session.cjs" ]]; then
  ROOT="$SCRIPT_DIR"
else
  ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

SAND_HOST="${SAND_HOST_DIR:-$HOME/sand-host}"
SRC="${XAI_SESSION_SRC:-$ROOT/xai-prompt-session.cjs}"
DEST="$SAND_HOST/xai-prompt-session.cjs"
COMPUTER_SRC="${CODEX_COMPUTER_SESSION_SRC:-$ROOT/codex-computer-session.cjs}"
COMPUTER_DEST="$SAND_HOST/codex-computer-session.cjs"
AUTO_REVIEW_SRC="${CODEX_AUTO_REVIEW_SRC:-$ROOT/codex-auto-review.cjs}"
AUTO_REVIEW_DEST="$SAND_HOST/codex-auto-review.cjs"
HOST_MAIN="$SAND_HOST/host-main.cjs"
BACKUP="$SAND_HOST/host-main.cjs.cursor-bak"
ENV_FILE="${SAND_DATA_DIR:-$HOME/sand-data}/xai-inference.env"
INJECT="$ROOT/inject-host.py"
[[ -f "$INJECT" ]] || INJECT="$SCRIPT_DIR/inject-host.py"

log() { printf '+ %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
copy_unless_same() {
  local src_abs dest_abs
  src_abs="$(readlink -f "$1")"
  dest_abs="$(readlink -f "$2" 2>/dev/null || true)"
  [[ "$src_abs" == "$dest_abs" ]] || cp "$1" "$2"
}

for required in "$HOST_MAIN" "$SRC" "$COMPUTER_SRC" "$AUTO_REVIEW_SRC" "$INJECT"; do
  [[ -f "$required" ]] || die "missing $required"
done

mkdir -p "$(dirname "$ENV_FILE")" "$SAND_HOST/scripts"
touch "$ENV_FILE"
if ! grep -q '^OPENGROK_DIRECT_BROWSER_MAIN=' "$ENV_FILE"; then
  printf 'OPENGROK_DIRECT_BROWSER_MAIN=1\n' >>"$ENV_FILE"
  log "enabled direct main-thread DOM/Computer tools"
fi

copy_unless_same "$SRC" "$DEST"
copy_unless_same "$COMPUTER_SRC" "$COMPUTER_DEST"
copy_unless_same "$AUTO_REVIEW_SRC" "$AUTO_REVIEW_DEST"
copy_unless_same "$INJECT" "$SAND_HOST/scripts/inject-host.py"
cp "$0" "$SAND_HOST/scripts/ensure-xai-inference.sh" 2>/dev/null || true
chmod +x "$SAND_HOST/scripts/ensure-xai-inference.sh" 2>/dev/null || true
log "installed routed prompt, Computer, and Auto-review modules"

python3 "$INJECT" "$HOST_MAIN" "$BACKUP"
node --check "$HOST_MAIN"
if grep -q createRoutedPromptSession "$HOST_MAIN" \
  && grep -q createRoutedComputerUseSession "$HOST_MAIN" \
  && grep -q createCodexAutoReviewClassifier "$HOST_MAIN" \
  && grep -Fq '  return "park";' "$HOST_MAIN" \
  && grep -Fq 'Use the browser_* DOM tools in this main turn directly' "$HOST_MAIN" \
  && grep -Fq 'Use Computer directly in this main turn' "$HOST_MAIN" \
  && grep -Fq 'Do not launch any Task subagent' "$HOST_MAIN" \
  && grep -Fq 'inspect the parent transcript pointer for repeated or continuing work' "$HOST_MAIN" \
  && grep -Fq 'tool.toolIdentifier.startsWith("BROWSER_")' "$HOST_MAIN"; then
  log "hook OK"
else
  die "hook injection failed"
fi
