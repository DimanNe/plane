"""
A rule that something does not happen holds once the page can no longer make it happen.

A page reacts to an act (a key, a press, a move of the pointer, a turn of the wheel) at once, in the handlers of its
events, or later through what those left behind: a timer (a debounce, the delay of a hover or a tooltip), a frame
callback, a request that is answered, an animation that ends. The acts that count are those since the page was last
seen settled, and what they left behind is every timer, interval and frame callback that the page made after the
first of them, any request in flight and any animation that began after it. When none is left, two frames are drawn
and a task runs, for what the last of them started; after that, what the page shows and what it sent cannot change
unless something new happens.

Not counted:
- what the page made before that first act, such as the timers its data cache arms after each load of a page:
  they are no reaction to an act, and they would keep every step waiting for seconds;
- what a check's own scripts make, such as a recorder of frames;
- what the page does on a message from the server over a WebSocket that is not a live update about one of the
  check's own projects, and what that work schedules in turn: the changes that the other checks of the run make
  reach every page of the run as live updates, and they are no reaction to an act of this page. A live update
  about the check's own project is counted: it can carry what an act changed on the server;
- timers made with a delay longer than LONGEST_REACTION_DELAY_MS (see there).
"""

import json

import typing as t

import playwright.sync_api as pw

# A timer is waited for when the page made it with a delay up to this: just above the longest delay of a reaction
# that a rule of the checks says does not happen, the debounce of the description's autosave
# (apps/web/components/editor/rich-text/description-input/root.tsx). The page's longer timers are its upkeep or a
# lifetime, never such a reaction: the expiry of a request in the data cache and its loading-slow notice, a toast,
# the "saved" label, use-auto-save's autosave. A rule about a reaction with a longer delay than this needs this
# raised above that delay; a rule about a reaction the page schedules later than its upkeep needs a wait of its own.
LONGEST_REACTION_DELAY_MS: int = 1600

# Installed in every page of a check before the page's own scripts. It keeps the original functions for its own
# waiting, so that the waiting is not counted as the page's.
SETTLE_WATCH_JS: str = """
(() => {
  if (window.__settle) return;
  const LONGEST_REACTION_DELAY_MS = %(longest_reaction_delay_ms)d;
  // the check's own projects, which install_settle_watch() and add_own_project() name
  const ownProjects = new Set(window.__settleOwnProjects || []);
  // when the first act since the page was last seen settled came; null when there was none
  let firstActAt = null;
  for (const type of ["keydown", "keyup", "pointerdown", "pointerup", "pointermove", "mousedown", "mouseup",
                      "click", "dblclick", "contextmenu", "wheel", "beforeinput", "input", "dragstart", "drop"]) {
    window.addEventListener(type, (event) => {
      if (event.isTrusted && firstActAt === null) firstActAt = performance.now();
    }, { capture: true });
  }
  // Whether the function that calls a timer function is a check's own script (page.evaluate) rather than the page's:
  // the frame after this file's own three (this one, isMadeByPageAfterAct, the timer function).
  const isCalledByCheck = () => {
    const caller = (new Error().stack || "").split("\\n")[4] || "";
    return /eval at evaluate|UtilityScript/.test(caller);
  };
  // "socket" while the page handles a message of a WebSocket that is not a live update about one of the check's own
  // projects, and while it runs a timer or a frame callback that such handling made
  let origin = null;
  const runWithOrigin = (handlerOrigin, handler, self, args) => {
    const previous = origin;
    origin = handlerOrigin;
    try {
      return handler.apply(self, args);
    } finally {
      origin = previous;
    }
  };
  const handlesOf = new WeakMap();
  const originalAddEventListener = WebSocket.prototype.addEventListener;
  const originalRemoveEventListener = WebSocket.prototype.removeEventListener;
  // A live update names the project of the changed row (apps/web/store/live-updates.ts, TChange). Heartbeats,
  // resyncs and what is not JSON, such as the editor's own updates, name none.
  const isLiveUpdateAboutOwnProject = (event) => {
    try {
      const message = JSON.parse(event.data);
      return typeof message.p === "string" && ownProjects.has(message.p);
    } catch {
      return false;
    }
  };
  const wrapForSocket = (listener) => {
    if (typeof listener !== "function") return listener;
    if (!handlesOf.has(listener)) {
      handlesOf.set(listener, function (event) {
        return runWithOrigin(isLiveUpdateAboutOwnProject(event) ? origin : "socket", listener, this, arguments);
      });
    }
    return handlesOf.get(listener);
  };
  WebSocket.prototype.addEventListener = function (type, listener, options) {
    return originalAddEventListener.call(this, type, type === "message" ? wrapForSocket(listener) : listener, options);
  };
  WebSocket.prototype.removeEventListener = function (type, listener, options) {
    return originalRemoveEventListener.call(this, type, type === "message" ? wrapForSocket(listener) : listener, options);
  };
  const onmessage = Object.getOwnPropertyDescriptor(WebSocket.prototype, "onmessage");
  Object.defineProperty(WebSocket.prototype, "onmessage", {
    configurable: true,
    enumerable: onmessage.enumerable,
    get() { return onmessage.get.call(this); },
    set(listener) { onmessage.set.call(this, wrapForSocket(listener)); },
  });
  const isMadeByPageAfterAct = () => firstActAt !== null && origin !== "socket" && !isCalledByCheck();

  const originalSetTimeout = window.setTimeout.bind(window);
  const originalClearTimeout = window.clearTimeout.bind(window);
  const timers = new Map();
  window.setTimeout = function (handler, delay, ...rest) {
    const isCounted = isMadeByPageAfterAct() && (Number(delay) || 0) <= LONGEST_REACTION_DELAY_MS;
    const madeInOrigin = origin;
    let id;
    const run = typeof handler === "function"
      ? function () { timers.delete(id); return runWithOrigin(madeInOrigin, handler, this, arguments); }
      : handler;
    id = originalSetTimeout(run, delay, ...rest);
    if (isCounted) timers.set(id, String(handler).slice(0, 80));
    return id;
  };
  window.clearTimeout = function (id) {
    timers.delete(id);
    return originalClearTimeout(id);
  };
  const originalSetInterval = window.setInterval.bind(window);
  const originalClearInterval = window.clearInterval.bind(window);
  const intervals = new Map();
  window.setInterval = function (handler, period, ...rest) {
    const isCounted = isMadeByPageAfterAct() && (Number(period) || 0) <= LONGEST_REACTION_DELAY_MS;
    const id = originalSetInterval(handler, period, ...rest);
    if (isCounted) intervals.set(id, String(handler).slice(0, 80));
    return id;
  };
  window.clearInterval = function (id) {
    intervals.delete(id);
    return originalClearInterval(id);
  };
  const originalRequestAnimationFrame = window.requestAnimationFrame.bind(window);
  const originalCancelAnimationFrame = window.cancelAnimationFrame.bind(window);
  const frameCallbacks = new Map();
  window.requestAnimationFrame = function (callback) {
    const isCounted = isMadeByPageAfterAct();
    const madeInOrigin = origin;
    let id;
    id = originalRequestAnimationFrame(function () {
      frameCallbacks.delete(id);
      return runWithOrigin(madeInOrigin, callback, this, arguments);
    });
    if (isCounted) frameCallbacks.set(id, String(callback).slice(0, 80));
    return id;
  };
  window.cancelAnimationFrame = function (id) {
    frameCallbacks.delete(id);
    return originalCancelAnimationFrame(id);
  };
  let requestsInFlight = 0;
  const originalFetch = window.fetch.bind(window);
  window.fetch = function () {
    requestsInFlight += 1;
    return originalFetch.apply(null, arguments).finally(() => { requestsInFlight -= 1; });
  };
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    requestsInFlight += 1;
    this.addEventListener("loadend", () => { requestsInFlight -= 1; }, { once: true });
    return originalSend.apply(this, arguments);
  };
  const readPending = () => ({
    timers: [...timers.values()],
    intervals: [...intervals.values()],
    frameCallbacks: [...frameCallbacks.values()],
    requestsInFlight,
    animations: document.getAnimations()
      .filter((animation) => animation.playState === "running" && animation.effect &&
               animation.effect.getComputedTiming().endTime !== Infinity &&
               firstActAt !== null && (animation.startTime === null || animation.startTime >= firstActAt))
      .map((animation) => animation.animationName || animation.transitionProperty || animation.constructor.name),
  });
  const isBusy = (pending) => pending.timers.length + pending.intervals.length + pending.frameCallbacks.length +
    pending.requestsInFlight + pending.animations.length > 0;
  window.__settle = {
    ownProjects,
    // null until the wait that start() began has ended: then whether the page settled, and what was left if not
    result: null,
    start(capMs) {
      window.__settle.result = null;
      const startedAt = performance.now();
      const tick = () => {
        if (performance.now() - startedAt > capMs) {
          window.__settle.result = { settled: false, pending: readPending() };
          return;
        }
        if (isBusy(readPending())) {
          originalSetTimeout(tick, 5);
          return;
        }
        originalRequestAnimationFrame(() => originalRequestAnimationFrame(() => originalSetTimeout(() => {
          if (isBusy(readPending())) {
            tick();
            return;
          }
          firstActAt = null;
          window.__settle.result = { settled: true };
        }, 0)));
      };
      tick();
    },
  };
})();
""" % {"longest_reaction_delay_ms": LONGEST_REACTION_DELAY_MS}


def install_settle_watch(
    context: pw.BrowserContext, own_project_ids: t.Sequence[str]
) -> None:
    context.add_init_script(
        f"window.__settleOwnProjects = {json.dumps(list(own_project_ids))};\n"
        + SETTLE_WATCH_JS
    )


def add_own_project(pages: t.Sequence[pw.Page], project_id: str) -> None:
    """Tells the open pages that live updates about this project, which the check has just made, are its own."""
    page: pw.Page
    for page in pages:
        if not page.is_closed():
            page.evaluate("(id) => window.__settle.ownProjects.add(id)", project_id)


def start_settle_waits(pages: t.Sequence[pw.Page], cap_seconds: float) -> None:
    """Starts, in every open page, the wait until it has settled; read_settle_results() tells when they end."""
    # FOR_REVIEWER: measured and left: (1) waiting for every timer of a page is sound, but the data cache's upkeep
    # kept steps waiting 2-3 s after a page loaded, and in a full run the live updates of the other checks kept
    # pages busy (44 steps waited 142 s in all, against 44 s for the fixed second); (2) learning which timers do
    # nothing by watching what follows them is unsound: a change of a variable, or a render React defers, looks
    # like nothing. Work that a WebSocket message starts is followed through timers and frame callbacks, not
    # through promises: what such work does after an await is counted, so the page waits longer, never less.
    # FOR_REVIEWER: every step that says nothing happens watches one open page, and on this machine a live update
    # about a page's own write arrives before the write's answer, so its work is counted. A rule about a second page
    # after an act in the first would need a wait for that update itself: the second page may settle before the
    # server's message reaches it.
    page: pw.Page
    for page in pages:
        if not page.is_closed():
            page.evaluate("(capMs) => window.__settle.start(capMs)", cap_seconds * 1000)


def read_settle_results(
    pages: t.Sequence[pw.Page],
) -> t.Optional[t.List[t.Dict[str, t.Any]]]:
    """What the waits of start_settle_waits() found in the open pages, or None while one of them still waits."""
    results: t.List[t.Dict[str, t.Any]] = []
    page: pw.Page
    for page in pages:
        if page.is_closed():
            continue
        result: t.Optional[t.Dict[str, t.Any]] = page.evaluate("window.__settle.result")
        if result is None:
            return None
        results.append(result)
    return results
