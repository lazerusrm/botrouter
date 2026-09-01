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

# This user-level preference fixes docks that are already running. It works on
# a fresh computer even when the bot does not have administrator access.
if command -v dconf >/dev/null 2>&1; then
  dconf write /net/launchpad/plank/docks/dock1/hide-mode "'autohide'" >/dev/null 2>&1 || true
  dconf write /net/launchpad/plank/docks/dock1/hide-delay 0 >/dev/null 2>&1 || true
  dconf write /net/launchpad/plank/docks/dock1/unhide-delay 10000 >/dev/null 2>&1 || true
fi

if [[ "$(id -u)" != 0 ]]; then
  if ! command -v sudo >/dev/null 2>&1 || ! sudo -n true 2>/dev/null; then
    pkill -x plank 2>/dev/null || true
    sleep 2
    echo "Automation dock auto-hidden for the current computer. Administrator access is needed to patch future desktop launches."
    exit 0
  fi
  elevate=(sudo -n)
fi
if [[ ! -f "$target" ]]; then
  pkill -x plank 2>/dev/null || true
  echo "No automation dock wrapper found; current dock preferences were updated."
  exit 0
fi

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
