#!/usr/bin/env bash
# Keep the automation desktop's full screen clickable.
set -euo pipefail

[[ "${1:-}" == "--yes" ]] || {
  echo "usage: $0 --yes" >&2
  exit 2
}

target=/usr/local/bin/box-plank
backup=/usr/local/lib/botrouter/box-plank.original
elevate=()
if [[ "$(id -u)" != 0 ]]; then
  command -v sudo >/dev/null 2>&1 || { echo "administrator access is required" >&2; exit 1; }
  elevate=(sudo -n)
  "${elevate[@]}" true
fi
[[ -f "$target" ]] || { echo "No automation dock wrapper found; nothing to change."; exit 0; }

"${elevate[@]}" install -d -m 755 "$(dirname "$backup")"
if [[ ! -f "$backup" ]]; then
  "${elevate[@]}" cp -a "$target" "$backup"
fi
replacement="$(mktemp)"
trap 'unlink "$replacement"' EXIT
printf '%s\n' \
  '#!/bin/sh' \
  '# BotRouter: keep the dock hidden during pixel automation.' \
  'dconf write /net/launchpad/plank/docks/dock1/hide-mode "'"'"'autohide'"'"'" >/dev/null 2>&1 || true' \
  'dconf write /net/launchpad/plank/docks/dock1/hide-delay 0 >/dev/null 2>&1 || true' \
  'dconf write /net/launchpad/plank/docks/dock1/unhide-delay 10000 >/dev/null 2>&1 || true' \
  "exec $backup \"\$@\"" >"$replacement"
"${elevate[@]}" install -m 755 "$replacement" "$target"

# Existing docks are already registered with the desktop supervisor. Ending
# them once makes the supervisor relaunch the auto-hide wrapper above.
pkill -x plank 2>/dev/null || "${elevate[@]}" pkill -x plank 2>/dev/null || true
sleep 2
echo "Automation dock auto-hidden; original saved at $backup"
