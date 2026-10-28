"""
The browser of a check, and what a person's hand does in any page.

A check gets a browser of its own: a headless one, or a real Chrome window started unseen
(claude/tools/offscreen_chrome.py). A real window draws differently from a headless browser, so
every check passes in both. A window is started for one check and stopped after it: one that has served many
checks stops giving pictures.
"""

import concurrent.futures
import contextlib
import os
import pathlib as pl
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import typing as t

import playwright.sync_api as pw

import instance as ins
import page_changes
import settle
import steps

OFFSCREEN_CHROME: pl.Path = ins.REPOSITORY / "claude/tools/offscreen_chrome.py"
WINDOW_START_TIMEOUT: float = 60
# what Chrome writes on its standard error once its debugging port takes connections
DEVTOOLS_LISTENING: re.Pattern[bytes] = re.compile(
    rb"DevTools listening on (ws://\S+)\n"
)
Point: t.TypeAlias = t.Tuple[float, float]


def copy_output_of_window_to_log(
    window: "subprocess.Popen[bytes]",
    log_path: pl.Path,
    debugging_address: "concurrent.futures.Future[str]",
) -> None:
    """Writes what the window's processes say to the log as they say it, until they have all ended. Chrome says there
    where its debugging port is once the port takes connections, and that address is given to `debugging_address`;
    a window that ends without saying it gives the way it ended."""
    assert window.stdout is not None
    log: t.BinaryIO
    with window.stdout, open(log_path, "wb") as log:
        line: bytes
        for line in window.stdout:
            log.write(line)
            log.flush()
            found: t.Optional[re.Match[bytes]] = DEVTOOLS_LISTENING.fullmatch(line)
            if found is not None and not debugging_address.done():
                debugging_address.set_result(found.group(1).decode())
    if not debugging_address.done():
        debugging_address.set_exception(
            RuntimeError(f"{OFFSCREEN_CHROME} ended with {window.wait()}")
        )


@contextlib.contextmanager
def open_real_window(
    playwright: pw.Playwright, directory: pl.Path
) -> t.Iterator[pw.Browser]:
    profile: pl.Path = directory / "chrome-profile"
    # Chrome makes a socket in TMPDIR, and the path of a socket may be no longer than about a hundred characters,
    # which the check's own directory can come near; so the window has a short one beside it
    temporary: pl.Path = pl.Path(tempfile.mkdtemp(prefix="w", dir=directory.parent))
    # in a session of its own, so that the compositor and Chrome are stopped together; on port 0, which Chrome
    # replaces with a free one
    window: subprocess.Popen[bytes] = subprocess.Popen(
        [str(OFFSCREEN_CHROME), "0", str(profile)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env={**os.environ, "TMPDIR": str(temporary)},
    )
    # FOR_REVIEWER: the port was one that find_free_port saw free, which another process could take before Chrome
    # did, and the port was then asked every 0.2 s whether it answered. Chrome now takes a free port itself and
    # says which once it listens.
    debugging_address: concurrent.futures.Future[str] = concurrent.futures.Future()
    threading.Thread(
        target=copy_output_of_window_to_log,
        args=(window, directory / "chrome.log", debugging_address),
        daemon=True,
    ).start()
    try:
        try:
            address: str = debugging_address.result(timeout=WINDOW_START_TIMEOUT)
        except TimeoutError:
            raise RuntimeError(
                f"Chrome did not open its debugging port in {WINDOW_START_TIMEOUT} s"
            ) from None
        yield playwright.chromium.connect_over_cdp(address)
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
    origin: t.Optional[str] = None,
) -> pw.Page:
    """A window of this size in which the account is signed in, at a path of the instance: at its own address, or at
    `origin`, another address of the host that reaches it."""
    url: str = origin if origin is not None else check.instance.url
    context: pw.BrowserContext = check.browser.new_context(
        viewport={"width": width, "height": height}
    )
    context.add_cookies(
        [
            {"name": name, "value": value, "url": url}
            for name, value in account.cookies.items()
        ]
    )
    page_changes.watch_page_changes(context)
    settle.install_settle_watch(context, [project.id for project in check.projects])
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
    page.goto(url + path)
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
