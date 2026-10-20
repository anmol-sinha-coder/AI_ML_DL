#!/usr/bin/env bash
# Take a numbered screenshot into screenshots/ using whatever tool is installed.
#   scripts/shot.sh 05_github_actions_run            # select an area/window interactively
#   scripts/shot.sh 07_docker_ps --delay 5           # wait 5 s first (time to switch windows)
#   scripts/shot.sh 07_docker_ps --full              # whole screen
# Install one of:  sudo apt install gnome-screenshot   (GNOME / Ubuntu)   |  flameshot  |  scrot  |  imagemagick
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
NAME="${1:?usage: shot.sh NAME [--delay N] [--full]}"; shift || true
DELAY=2; FULL=0
while [ $# -gt 0 ]; do case "$1" in --delay) DELAY="$2"; shift ;; --full) FULL=1 ;; esac; shift; done
OUT="screenshots/${NAME}.png"; mkdir -p screenshots
echo "Capturing in ${DELAY}s -> ${OUT}"; sleep "$DELAY"
if command -v gnome-screenshot >/dev/null; then
  if [ "$FULL" -eq 1 ]; then gnome-screenshot -f "$OUT"; else gnome-screenshot -a -f "$OUT"; fi
elif command -v flameshot >/dev/null; then
  if [ "$FULL" -eq 1 ]; then flameshot full -p screenshots -r > "$OUT"; else flameshot gui -p "$OUT"; fi
elif command -v grim >/dev/null; then
  if [ "$FULL" -eq 1 ]; then grim "$OUT"; else grim -g "$(slurp)" "$OUT"; fi
elif command -v scrot >/dev/null; then
  if [ "$FULL" -eq 1 ]; then scrot "$OUT"; else scrot -s "$OUT"; fi
elif command -v import >/dev/null; then
  if [ "$FULL" -eq 1 ]; then import -window root "$OUT"; else import "$OUT"; fi
else
  echo "No screenshot tool found. Install: sudo apt install gnome-screenshot" >&2; exit 1
fi
echo "saved ${OUT}"
