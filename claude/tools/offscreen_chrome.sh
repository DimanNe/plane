#!/bin/sh
# Starts Google Chrome as a real window that nobody sees, inside an off-screen Wayland compositor, with a
# debugging port that Playwright connects to (chromium.connect_over_cdp).
#
# A headless browser does not draw the way a window does. A view transition that ends in a headless browser never
# ended in a window of a Chrome started with --disable-frame-rate-limit, and the page stopped being drawn. What
# moves on the page is therefore also tried here, with the flags the owner's Chrome is started with.
#
# The off-screen compositor has no pointing device, and Chrome would then report that nothing can hover: every
# hover style of the page would be off. The window is told that it has a mouse, as the owner's has.
# usage: claude/tools/offscreen_chrome.sh <debugging-port> <profile-dir> [flags of Chrome...]
set -eu
PORT="$1"
PROFILE="$2"
shift 2
SOCKET="wl-offscreen-$PORT"
# where the compositor puts its socket; a session without a login manager has none set
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
weston --backend=headless --socket="$SOCKET" --width=1500 --height=950 --no-config --idle-time=0 &
WESTON=$!
trap 'kill "$WESTON" 2>/dev/null' EXIT INT TERM
sleep 1
WAYLAND_DISPLAY="$SOCKET" google-chrome --ozone-platform=wayland --remote-debugging-port="$PORT" \
    --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check --disable-dev-shm-usage \
    --window-size=1440,900 \
    --blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4 \
    "$@" about:blank
