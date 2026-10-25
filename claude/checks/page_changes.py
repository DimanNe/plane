"""
A step that has to read a page again reads it when the page has changed, never by the clock.

What a check reads of a page can change only through something the page does: the DOM changes, an element gets
or loses the focus, something scrolls, a script sets the value of a field, an animation starts or ends, a
request goes out or its answer comes back (what the server stores changes with the requests of the pages). A
watch in every page counts these changes. After the first change that the page has not told of yet, a wait returns
at the first frame that the page draws without a change: one read then sees all that a burst of changes did, and
reads do not take turns with a page that is still busy (read after every frame that changed, a page load was read
some 30 times). A step that says something does not happen reads after every frame that changed, so that a change
that comes and goes is seen. The deadline only bounds a step that fails. Reading by the clock read every 50 ms, or
every 500 ms once Playwright's own waits had waited for a while: late by up to that much after the page was right,
and again and again while it was slow.

A check reads one page at a time, but a step can wait for a page other than the one it acted on (a change made in
one session shows in another). A wait blocks on one open page; every other open page tells by a console message
that it has changed, and the handler of that message ends the wait (see watch_page_changes).
"""

import dataclasses as dc
import time
import typing as t

import playwright.sync_api as pw

# As long as Playwright's own waits wait before they fail.
WAIT_TIMEOUT: float = 30
PAGE_CHANGED_MESSAGE: str = "checks: the page changed"

# Installed in every page of a check before the page's own scripts, and before the watch of settle.py, so that
# its timers are none of those that settle.py waits for.
PAGE_CHANGE_WATCH_JS: str = """
(() => {
  if (window.__pageChanges) return;
  const PAGE_CHANGED_MESSAGE = %(message)s;
  const originalSetTimeout = window.setTimeout.bind(window);
  const originalClearTimeout = window.clearTimeout.bind(window);
  const originalRequestAnimationFrame = window.requestAnimationFrame.bind(window);
  const originalConsoleDebug = console.debug.bind(console);
  let changes = 0;
  // the changes that a wait or a console message has told of
  let toldChanges = 0;
  // what the wait under way does on the next change
  let onChange = null;
  // whether the next change is told by a console message, for a wait on another page of the check
  let isTellingByConsole = false;
  // A page that is not shown draws no frames.
  const onNextFrame = (callback) => {
    if (document.visibilityState === "hidden") originalSetTimeout(callback, 0);
    else originalRequestAnimationFrame(callback);
  };
  // Runs `then` after the first frame that the page draws without a change, or with `isEachFrame` after the next
  // frame, whether it changed or not.
  const afterFrame = (isEachFrame, then) => {
    let changesBefore = changes;
    const look = () => {
      if (!isEachFrame && changes > changesBefore) {
        changesBefore = changes;
        onNextFrame(look);
      } else {
        originalSetTimeout(then, 0);
      }
    };
    onNextFrame(look);
  };
  const tellByConsole = () => afterFrame(false, () => {
    toldChanges = changes;
    originalConsoleDebug(PAGE_CHANGED_MESSAGE);
  });
  const count = () => {
    changes += 1;
    if (isTellingByConsole) {
      isTellingByConsole = false;
      tellByConsole();
    }
    if (onChange) onChange();
  };
  new MutationObserver(count).observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  for (const type of ["input", "change", "focusin", "focusout", "scroll", "mouseover", "mouseout", "load", "error",
                      "toggle", "resize", "transitionrun", "transitionend", "transitioncancel", "animationstart",
                      "animationend", "animationcancel", "checks-settled"]) {
    window.addEventListener(type, count, { capture: true, passive: true });
  }
  document.addEventListener("selectionchange", count);
  // a script that sets the value of a field changes no attribute and fires no event
  for (const [prototype, property] of [[HTMLInputElement.prototype, "value"], [HTMLInputElement.prototype, "checked"],
                                       [HTMLTextAreaElement.prototype, "value"], [HTMLSelectElement.prototype, "value"]]) {
    const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
    Object.defineProperty(prototype, property, { ...descriptor, set(value) { descriptor.set.call(this, value); count(); } });
  }
  // an animation that a script starts fires no event of the DOM, when it starts or when it ends
  const originalAnimate = Element.prototype.animate;
  Element.prototype.animate = function () {
    const animation = originalAnimate.apply(this, arguments);
    count();
    animation.finished.then(count, count);
    return animation;
  };
  const originalFetch = window.fetch;
  window.fetch = function () {
    count();
    return originalFetch.apply(this, arguments).finally(count);
  };
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    count();
    this.addEventListener("loadend", count, { once: true });
    return originalSend.apply(this, arguments);
  };
  const wait = (capMs, isEachFrame) => new Promise((resolve) => {
    let hasEnded = false;
    const end = () => {
      if (hasEnded) return;
      hasEnded = true;
      originalClearTimeout(cap);
      if (onChange === start) onChange = null;
      toldChanges = changes;
      resolve();
    };
    const cap = originalSetTimeout(end, capMs);
    const start = () => {
      onChange = null;
      afterFrame(isEachFrame, end);
    };
    if (changes > toldChanges) start();
    else onChange = start;
  });
  window.__pageChanges = {
    wait,
    tellNextChangeByConsole() {
      if (changes > toldChanges) tellByConsole();
      else isTellingByConsole = true;
    },
    // ends the wait under way, for a change of another page
    endWait() {
      if (onChange) onChange();
    },
    // the first truthy result of `read`, which is read now and after each change, or the last one read at the cap
    async waitUntilTrue(read, capMs) {
      const deadline = performance.now() + capMs;
      let result = read();
      while (!result && performance.now() < deadline) {
        await wait(deadline - performance.now(), true);
        result = read();
      }
      return result;
    },
  };
})();
""" % {"message": repr(PAGE_CHANGED_MESSAGE)}


@dc.dataclass
class WaitOnPages:
    """What the console handlers of the pages of this process's check need to end a wait: checks run one in a
    process."""

    page_waited_on: t.Optional[pw.Page] = None
    # A page told of a change while no wait was under way: after the step's last read, or during it.
    has_page_changed_unseen: bool = False


WAIT_ON_PAGES: WaitOnPages = WaitOnPages()


def end_wait_for_change_of_another_page(message: pw.ConsoleMessage) -> None:
    if message.text != PAGE_CHANGED_MESSAGE:
        return
    page: t.Optional[pw.Page] = WAIT_ON_PAGES.page_waited_on
    if page is None:
        WAIT_ON_PAGES.has_page_changed_unseen = True
        return
    try:
        page.evaluate("() => window.__pageChanges.endWait()")
    except pw.Error:
        # the page waited on has closed or navigated, which ends its wait as well
        pass


def watch_page_changes(context: pw.BrowserContext) -> None:
    """Makes every page of the context count its changes, and tell them to a wait that blocks on another page.
    Called before the context has a page, and before settle.install_settle_watch()."""
    context.add_init_script(PAGE_CHANGE_WATCH_JS)
    context.on(
        "page",
        lambda page: page.on("console", end_wait_for_change_of_another_page),
    )


def wait_for_page_change(
    pages: t.Sequence[pw.Page], deadline: float, is_each_frame: bool = False
) -> None:
    """Returns at the first frame without a change after a change of one of the open pages that it has not told of
    yet, or with `is_each_frame` at the frame after that change; at the latest at the deadline (of
    time.monotonic())."""
    open_pages: t.List[pw.Page] = [page for page in pages if not page.is_closed()]
    if not open_pages:
        # FOR_REVIEWER: no step of the checks gets here. A step that reads the server after its pages have closed
        # waits for nothing that the check does; were one needed, it would wait for the event it expects.
        raise RuntimeError(
            "No page of the check is open that could change what the step reads"
        )
    other: pw.Page
    try:
        for other in open_pages[1:]:
            other.evaluate("() => window.__pageChanges.tellNextChangeByConsole()")
        # what the other pages told before they answered has been handled by now
        if WAIT_ON_PAGES.has_page_changed_unseen:
            WAIT_ON_PAGES.has_page_changed_unseen = False
            return
        WAIT_ON_PAGES.page_waited_on = open_pages[0]
        open_pages[0].evaluate(
            "([capMs, isEachFrame]) => window.__pageChanges.wait(capMs, isEachFrame)",
            [max(0.0, deadline - time.monotonic()) * 1000, is_each_frame],
        )
    except pw.Error:
        # a page that navigates or closes meanwhile has changed too
        pass
    finally:
        WAIT_ON_PAGES.page_waited_on = None


def wait_until_true(
    page: pw.Page, js: str, arg: t.Any = None, timeout: float = WAIT_TIMEOUT
) -> t.Any:
    """page.wait_for_function() that reads the function again on each change of the page instead of each frame;
    returns its first truthy result."""
    deadline: float = time.monotonic() + timeout
    while True:
        try:
            result: t.Any = page.evaluate(
                f"([arg, capMs]) => window.__pageChanges.waitUntilTrue(() => ({js})(arg), capMs)",
                [arg, max(0.0, deadline - time.monotonic()) * 1000],
            )
        except pw.Error as error:
            # a document that the page leaves takes its wait with it; the function is read in the next one
            if (
                "context was destroyed" not in str(error)
                or time.monotonic() >= deadline
            ):
                raise
            continue
        if result:
            return result
        raise TimeoutError(f"{js.strip()} was not true after {timeout:.0f} s")


def wait_until_shown(locator: pw.Locator, timeout: float = WAIT_TIMEOUT) -> None:
    """locator.wait_for(): until an element of the locator is visible."""
    deadline: float = time.monotonic() + timeout
    while not locator.is_visible():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"{locator} was not shown after {timeout:.0f} s")
        wait_for_page_change([locator.page], deadline)


def wait_until_removed(locator: pw.Locator, timeout: float = WAIT_TIMEOUT) -> None:
    """locator.wait_for(state="detached"): until no element of the page is one of the locator."""
    deadline: float = time.monotonic() + timeout
    while locator.count() > 0:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"{locator} was still there after {timeout:.0f} s")
        wait_for_page_change([locator.page], deadline)
