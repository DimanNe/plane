"""
The browser of a check, and what a person's hand does in any page.

A check gets a browser of its own: a headless one, or a real Chrome window started unseen with the flag of the
owner's Chrome (claude/tools/offscreen_chrome.sh). A real window draws differently from a headless browser, so
every check passes in both. A window is started for one check and stopped after it: one that has served many
checks stops giving pictures.
"""

import contextlib
import os
import pathlib as pl
import shutil
import signal
import socket
import subprocess
import time
import typing as t
import urllib.error
import urllib.request

import playwright.sync_api as pw

import instance as ins
import settle
import steps

OFFSCREEN_CHROME: pl.Path = ins.REPOSITORY / "claude/tools/offscreen_chrome.sh"
WINDOW_START_TIMEOUT: float = 60
Point: t.TypeAlias = t.Tuple[float, float]


def find_free_port() -> int:
    listener: socket.socket
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for_debugging_port(port: int, window: "subprocess.Popen[bytes]") -> None:
    deadline: float = time.monotonic() + WINDOW_START_TIMEOUT
    while time.monotonic() < deadline:
        if window.poll() is not None:
            raise RuntimeError(f"{OFFSCREEN_CHROME} ended with {window.returncode}")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f"Chrome did not open port {port} in {WINDOW_START_TIMEOUT} s")


@contextlib.contextmanager
def open_real_window(
    playwright: pw.Playwright, directory: pl.Path
) -> t.Iterator[pw.Browser]:
    port: int = find_free_port()
    profile: pl.Path = directory / "chrome-profile"
    # Chrome makes a socket in TMPDIR, and the path of a socket may be no longer than about a hundred characters,
    # which the check's own directory can come near; so the window has a short one beside it
    temporary: pl.Path = directory.parent / f"w{port}"
    temporary.mkdir(exist_ok=True)
    log: t.BinaryIO
    with open(directory / "chrome.log", "wb") as log:
        # in a session of its own, so that the script, the compositor and Chrome are stopped together
        window: subprocess.Popen[bytes] = subprocess.Popen(
            [
                str(OFFSCREEN_CHROME),
                str(port),
                str(profile),
                "--disable-frame-rate-limit",
            ],
            stdout=log,
            stderr=log,
            start_new_session=True,
            env={**os.environ, "TMPDIR": str(temporary)},
        )
        try:
            wait_for_debugging_port(port, window)
            yield playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        finally:
            # a window that could not start under a heavy load has ended already, with its session
            with contextlib.suppress(ProcessLookupError):
                os.killpg(window.pid, signal.SIGTERM)
            window.wait()
            shutil.rmtree(profile, ignore_errors=True)
            shutil.rmtree(temporary, ignore_errors=True)


@contextlib.contextmanager
def open_browser(
    playwright: pw.Playwright, is_real_window: bool, directory: pl.Path
) -> t.Iterator[pw.Browser]:
    if is_real_window:
        browser: pw.Browser
        with open_real_window(playwright, directory) as browser:
            yield browser
        return
    # with its scroll bars, which take their width from the page as they do in a window
    browser = playwright.chromium.launch(
        args=["--disable-dev-shm-usage", "--disable-gpu"],
        ignore_default_args=["--hide-scrollbars"],
    )
    try:
        yield browser
    finally:
        browser.close()


def open_page(
    check: steps.Check,
    account: ins.Account,
    path: str,
    width: int = 1440,
    height: int = 900,
) -> pw.Page:
    """A window of this size in which the account is signed in, at a path of the instance."""
    context: pw.BrowserContext = check.browser.new_context(
        viewport={"width": width, "height": height}
    )
    context.add_cookies(
        [
            {"name": name, "value": value, "url": check.instance.url}
            for name, value in account.cookies.items()
        ]
    )
    settle.install_settle_watch(context)
    page: pw.Page = context.new_page()
    page.on(
        "pageerror",
        lambda error: check.page_errors.append(f"{error} (at {page.url})"),
    )
    page.on(
        "response",
        lambda response: check.server_errors.append(
            f"{response.status} {response.request.method} {response.url}"
        )
        if response.status >= 500
        else None,
    )
    check.pages.append(page)
    page.goto(check.instance.url + path)
    return page


def get_point(locator: pw.Locator, across: float = 0.5, down: float = 0.5) -> Point:
    """A point of an element, as parts of its width and height, after the page has brought it into view."""
    locator.scroll_into_view_if_needed()
    box: t.Optional[pw.FloatRect] = locator.bounding_box()
    if box is None:
        raise RuntimeError(f"{locator} is not on the page")
    return box["x"] + box["width"] * across, box["y"] + box["height"] * down


def let_page_draw(page: pw.Page) -> None:
    """Returns when the page has drawn what the last pointer move or key caused: two frames later."""
    page.evaluate(
        "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )


def press_and_carry(page: pw.Page, start: Point) -> None:
    """Presses at a point and moves off it, which is when the browser begins to drag what is there."""
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(start[0] + 6, start[1] + 4, steps=4)


def carry_to(page: pw.Page, point: Point) -> None:
    """Brings what is carried to a point as a hand does, with a last small move onto it."""
    page.mouse.move(point[0] - 2, point[1], steps=8)
    page.mouse.move(*point, steps=2)
    let_page_draw(page)


def record_writes(page: pw.Page) -> t.List[str]:
    """From now on, every request of the page that changes something on the server: method and path. Read it with
    `read_writes`."""
    writes: t.List[str] = []
    page.on(
        "request",
        lambda request: writes.append(
            f"{request.method} {request.url.split('/api/', 1)[-1]}"
        )
        if request.method not in ("GET", "HEAD", "OPTIONS") and "/api/" in request.url
        else None,
    )
    return writes


def read_writes(page: pw.Page, writes: t.List[str]) -> t.List[str]:
    """The requests written down so far. Playwright tells of a request only while it is called, so the page is
    asked something first."""
    page.evaluate("() => 0")
    return list(writes)
