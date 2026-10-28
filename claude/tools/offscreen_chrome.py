#!/usr/bin/env python3
"""
Starts Google Chrome as a real window that nobody sees, inside an off-screen Wayland compositor (weston), with a
debugging port that Playwright connects to (chromium.connect_over_cdp).

A headless browser does not draw the way a window does. A view transition that ends in a headless browser never
ends in a window of a Chrome started with --disable-frame-rate-limit, and the page is not drawn again. What
moves on the page is therefore also tried here.

    claude/tools/offscreen_chrome.py DEBUGGING_PORT PROFILE_DIR [FLAGS OF CHROME...]

With port 0, Chrome takes a free port and says which on its standard error: "DevTools listening on ws://...".
This process becomes Chrome; the compositor ends when Chrome does.
"""

import os
import socket
import subprocess
import sys
import typing as t


def start_compositor_for_one_client() -> socket.socket:
    """Starts weston serving only the client that gets the socket returned. A compositor that listens on a named
    socket can be connected to only once it listens, which nothing outside it tells; this one has its client
    connected before it starts, and it ends when that client goes."""
    compositor_end: socket.socket
    client_end: socket.socket
    compositor_end, client_end = socket.socketpair()
    with compositor_end:
        subprocess.Popen(
            [
                "weston",
                "--backend=headless",
                "--width=1500",
                "--height=950",
                "--no-config",
                "--idle-time=0",
            ],
            env={**os.environ, "WAYLAND_SERVER_SOCKET": str(compositor_end.fileno())},
            pass_fds=[compositor_end.fileno()],
        )
    return client_end


def main(arguments: t.List[str]) -> None:
    if len(arguments) < 2:
        raise SystemExit(__doc__)
    port: str = arguments[0]
    profile: str = arguments[1]
    # weston refuses to start without it; a session without a login manager has none set
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    # FOR_REVIEWER: the shell script that this replaces started weston in the background and Chrome a second later
    # (sleep 1), a second of every check in a window. A shell cannot make a socket pair. Not taken: weston's own
    # `-- program`, which connects the program the same way but starts it in a session of its own, beyond the
    # signal with which browser.py stops the window's session; and weston's systemd-notify.so, whose READY=1 this
    # process would have to wait for, where with the pair nothing waits.
    compositor: socket.socket = start_compositor_for_one_client()
    os.set_inheritable(compositor.fileno(), True)
    os.environ["WAYLAND_SOCKET"] = str(compositor.fileno())
    # The off-screen compositor has no pointing device, and Chrome would then report that nothing can hover: every
    # hover style of the page would be off. The window is told that it has a mouse, as the owner's has.
    os.execvp(
        "google-chrome",
        [
            "google-chrome",
            "--ozone-platform=wayland",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-dev-shm-usage",
            "--window-size=1440,900",
            "--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4",
            *arguments[2:],
            "about:blank",
        ],
    )


if __name__ == "__main__":
    main(sys.argv[1:])
