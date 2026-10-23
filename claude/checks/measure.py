#!/usr/bin/env python3
"""
Measures, on a running instance, what was made fast by measuring: typing in the description of a work item, the
Display pop-up, the dialog of a new work item, opening the timeline of some hundreds of work items, and dragging and
the wheel there. It builds its
own data in a workspace of its own, prints the numbers with the machine's load beside them, and judges nothing: a
change near these is measured before and after, on the same machine at the same load.

    claude/checks/measure.py --run-dir RUN_DIR [--windows] [--work-items 300]

Times are those of the main thread of the page, as Chrome counts them: by the clock, and as processor time, which
the load of other programs stretches less.
"""

import argparse
import collections
import json
import os
import pathlib as pl
import statistics
import sys
import time
import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import list_layout as ll
import steps

TRACE_CATEGORIES: t.List[str] = [
    "devtools.timeline",
    "disabled-by-default-devtools.timeline",
]
METRICS: t.Tuple[str, ...] = (
    "TaskDuration",
    "ScriptDuration",
    "RecalcStyleDuration",
    "LayoutDuration",
)
# How long a group of the timeline's plan is: the tasks of a group follow one another, and the first of each group
# follows the first of the group before, so that a drag of the very first task moves them all.
GROUP: int = 10
# Counts the frames the page draws from now on.
COUNT_FRAMES_JS: str = """
() => {
  window.__frames = [];
  const count = (time) => { window.__frames.push(time); window.__counting = requestAnimationFrame(count); };
  window.__counting = requestAnimationFrame(count);
}
"""
STOP_COUNTING_JS: str = (
    "() => { cancelAnimationFrame(window.__counting); return window.__frames; }"
)


# From the press of I to the caret in the title of the dialog that N I opens, by the page's clock.
TIME_TO_TITLE_JS: str = """
() => {
  window.__msToTitle = undefined;
  const pressed = (event) => {
    if (event.key !== 'i') return;
    document.removeEventListener('keydown', pressed, true);
    const start = performance.now();
    const focused = (event) => {
      if (event.target.name !== 'name') return;
      window.__msToTitle = performance.now() - start;
      document.removeEventListener('focusin', focused, true);
    };
    document.addEventListener('focusin', focused, true);
  };
  document.addEventListener('keydown', pressed, true);
}
"""


def read_load() -> str:
    return open("/proc/loadavg").read().split()[0]


def read_metrics(cdp: pw.CDPSession) -> t.Dict[str, float]:
    values: t.Dict[str, float] = {
        metric["name"]: metric["value"]
        for metric in cdp.send("Performance.getMetrics")["metrics"]
    }
    return {name: values[name] for name in METRICS}


def describe_frames(times: t.List[float]) -> str:
    gaps: t.List[float] = [after - before for before, after in zip(times, times[1:])]
    if not gaps:
        return "no frames"
    return f"frames {len(gaps)}, apart: median {statistics.median(gaps):.1f} ms, longest {max(gaps):.1f}"


def measure_counters(
    page: pw.Page, cdp: pw.CDPSession, label: str, act: t.Callable[[], None], count: int
) -> None:
    """Chrome's own counters of the main thread around an act, per one of its `count` parts."""
    page.evaluate(COUNT_FRAMES_JS)
    before: t.Dict[str, float] = read_metrics(cdp)
    act()
    browser.let_page_draw(page)
    after: t.Dict[str, float] = read_metrics(cdp)
    per: t.Dict[str, float] = {
        name: (after[name] - before[name]) * 1000 / count for name in METRICS
    }
    print(
        f"  {label}: main thread {per['TaskDuration']:.1f} ms each (script {per['ScriptDuration']:.1f}, styles "
        f"{per['RecalcStyleDuration']:.1f}, layout {per['LayoutDuration']:.1f}); "
        f"{describe_frames(page.evaluate(STOP_COUNTING_JS))}; load {read_load()}"
    )


def measure_traced(
    check: steps.Check, page: pw.Page, label: str, act: t.Callable[[], None], count: int
) -> None:
    """The main thread's work around an act, from Chrome's trace, per one of its `count` parts."""
    page.evaluate(COUNT_FRAMES_JS)
    check.browser.start_tracing(page=page, categories=TRACE_CATEGORIES)
    act()
    browser.let_page_draw(page)
    events: t.List[t.Dict[str, t.Any]] = json.loads(check.browser.stop_tracing())[
        "traceEvents"
    ]
    threads: t.Dict[t.Tuple[int, int], str] = {
        (event["pid"], event["tid"]): event["args"]["name"]
        for event in events
        if event.get("name") == "thread_name"
    }
    clock: t.Counter[str] = collections.Counter()
    processor: t.Counter[str] = collections.Counter()
    event: t.Dict[str, t.Any]
    for event in events:
        if (
            event.get("ph") == "X"
            and threads.get((event["pid"], event["tid"])) == "CrRendererMain"
        ):
            clock[event["name"]] += event.get("dur", 0) / 1000
            processor[event["name"]] += event.get("tdur", 0) / 1000
    print(
        f"  {label}: main thread {clock['RunTask'] / count:.2f} ms each by the clock, {processor['RunTask'] / count:.2f} "
        f"ms of processor time (in the handlers of events {processor['EventDispatch'] / count:.2f}, styles "
        f"{processor['UpdateLayoutTree'] / count:.2f}, layout {processor['Layout'] / count:.2f}, paint "
        f"{processor['Paint'] / count:.2f}); {describe_frames(page.evaluate(STOP_COUNTING_JS))}; load {read_load()}"
    )


def measure_typing_and_popup(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance, project, [{"name": f"line {number}"} for number in range(40)]
    )
    page: pw.Page = ll.open_list(check, account, project)
    cdp: pw.CDPSession = page.context.new_cdp_session(page)
    cdp.send("Performance.enable")
    elements: int = page.evaluate("() => document.querySelectorAll('*').length")
    print(f"the List layout of 40 work items, {elements} elements on the page:")
    display: pw.Locator = page.get_by_role("button", name="Display").first
    pop_up: pw.Locator = page.locator('[role="dialog"]').filter(has_text="Order by")

    def open_pop_up() -> None:
        display.click()
        pop_up.last.wait_for()

    def close_pop_up() -> None:
        page.keyboard.press("Escape")
        pop_up.first.wait_for(state="detached")

    run: int
    for run in range(1, 4):
        measure_counters(
            page, cdp, f"the Display pop-up opened ({run})", open_pop_up, 1
        )
        measure_counters(page, cdp, f"and closed by Escape ({run})", close_pop_up, 1)

    def open_dialog() -> None:
        ll.open_create_dialog(page)

    def close_dialog() -> None:
        page.keyboard.press("Escape")
        page.locator(ll.CREATE_DIALOG).wait_for(state="detached")

    for run in range(1, 4):
        page.evaluate(TIME_TO_TITLE_JS)
        measure_counters(
            page,
            cdp,
            f"the dialog of a new work item opened by N I ({run})",
            open_dialog,
            1,
        )
        print(
            f"    the caret in its title {page.evaluate('() => window.__msToTitle'):.1f} ms after I"
        )
        measure_counters(page, cdp, f"and closed by Escape ({run})", close_dialog, 1)
    ll.select_line(page, "line 3")
    page.keyboard.press("Enter")
    page.locator(ll.PANEL_TITLE).wait_for()
    editor: pw.Locator = page.locator(
        '#full-screen-portal .ProseMirror[contenteditable="true"]'
    ).first
    editor.click()
    for run in range(1, 3):
        measure_counters(
            page,
            cdp,
            f"40 keys typed in the description beside the list ({run})",
            lambda: page.keyboard.type("a" * 40, delay=33),
            40,
        )
    page.context.close()


def make_timeline_plan(
    check: steps.Check, project: ins.Project, count: int
) -> t.List[str]:
    """Groups of tasks with dates, a sub-work item each but the first, every task following the one before; returns the
    names of the first tasks of the groups."""
    tasks: t.List[ins.JSONObject] = []
    arrows: t.List[chart.Arrow] = []
    firsts: t.List[str] = []
    group: int
    for group in range(-(-count // GROUP)):
        start: int = (group * 3) % 60
        firsts.append(f"task {group:02d}.0")
        index: int
        for index in range(GROUP):
            name: str = f"task {group:02d}.{index}"
            tasks.append(
                {
                    "name": name,
                    "start_date": chart.day(start + index * 4),
                    "target_date": chart.day(start + index * 4 + 2 + index % 3),
                    "is_start_fixed": index == 0 and group == 0,
                    "description_html": f"<p>What task {index} of group {group} is about, in a sentence long enough to be cut</p>",
                    **({"parent": f"task {group:02d}.0"} if index else {}),
                }
            )
            if index:
                arrows.append((f"task {group:02d}.{index - 1}", name, "end-start", 0))
        if group:
            arrows.append((firsts[-2], firsts[-1], "start-start", 3))
    chart.make_plan(check.instance, project, tasks, arrows)
    return firsts


def measure_timeline(check: steps.Check, account: ins.Account, count: int) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    started: float = time.monotonic()
    make_timeline_plan(check, project, count)
    print(
        f"the timeline of {count} work items, made in {time.monotonic() - started:.0f} s:"
    )
    path: str = f"/{check.instance.workspace}/projects/{project.id}/issues/"
    page: pw.Page = chart.open_timeline(
        check, account, project, arrows=1, order_by="-created_at"
    )
    first_lines: t.List[float] = []
    for _ in range(5):
        page.goto("about:blank")
        page.goto(check.instance.url + path, wait_until="commit")
        page.locator(chart.LINE).first.wait_for()
        first_lines.append(page.evaluate("performance.now()"))
    print(
        f"  opened five times: the first line drawn after {statistics.median(first_lines):.0f} ms (median), "
        f"{min(first_lines):.0f} at best; load {read_load()}"
    )
    page.locator(".vertical-scrollbar.isolate div.top-7").first.wait_for()
    page.locator(chart.BAR).nth(10).wait_for()

    # the task that every other one follows was made first, so it is at the bottom of a list ordered newest first,
    # which the page loads a part at a time as the list is scrolled down
    _: int
    for _ in range(30):
        if chart.line(page, "task 00.0").count():
            break
        page.locator(".vertical-scrollbar.isolate").evaluate(
            "(element) => element.scrollTo(0, element.scrollHeight)"
        )
        page.wait_for_timeout(500)
    # the first task starts today, and Today puts today in the middle of the chart, whatever the first view was
    page.get_by_role("button", name="Today", exact=True).click()
    chart.bar(page, "task 00.0").wait_for()
    point: browser.Point = chart.get_bar_point(page, "task 00.0")
    px_per_day: float = chart.read_px_per_day_at_rest(page)
    page.mouse.move(*point)
    page.mouse.down()
    page.mouse.move(point[0] + 6, point[1])

    def drag_day_by_day() -> None:
        number: int
        for number in range(1, 61):
            page.mouse.move(point[0] + 6 + (number % 20) * px_per_day, point[1])
            browser.let_page_draw(page)

    measure_traced(
        check,
        page,
        "the first task dragged a day at a time, every task following, per move",
        drag_day_by_day,
        60,
    )
    page.keyboard.press("Escape")
    chart.let_go(page)

    empty: browser.Point = chart.find_empty_point(page)
    measure_traced(
        check,
        page,
        "the wheel, a notch at a time, per notch",
        lambda: chart.turn_wheel(page, empty, 20),
        20,
    )
    page.context.close()


def parse_arguments(arguments: t.List[str]) -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--run-dir", type=pl.Path, required=True, help="directory of a running instance"
    )
    parser.add_argument(
        "--windows",
        action="store_true",
        help="a real Chrome window in place of a headless browser",
    )
    parser.add_argument(
        "--work-items",
        type=int,
        default=300,
        help="how many work items the timeline has",
    )
    return parser.parse_args(arguments)


def main(arguments: t.List[str]) -> int:
    parsed: argparse.Namespace = parse_arguments(arguments)
    lock: t.TextIO = ins.lock_instance(parsed.run_dir)
    instance: ins.Instance = ins.open_instance(parsed.run_dir)
    directory: pl.Path = instance.run_dir / "checks" / "measure"
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(directory)
    playwright: pw.Playwright
    opened: pw.Browser
    with pw.sync_playwright() as playwright:
        with browser.open_browser(playwright, parsed.windows, directory) as opened:
            check: steps.Check = steps.Check("measure", instance, opened, directory)
            account: ins.Account = check.account()
            measure_typing_and_popup(check, account)
            measure_timeline(check, account, parsed.work_items)
            project: ins.Project
            for project in check.projects:
                ins.remove_project(instance, project)
    ins.close_instance(instance)
    lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
