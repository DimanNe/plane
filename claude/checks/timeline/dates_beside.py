"""
A bar under the pointer shows, a moment after the pointer came, its start and its end beside it and the days it
lasts on a dimension line as wide as the bar, until a moment after the pointer left it; a pointer that sweeps
across bars shows nothing. A dragged bar keeps them wherever the pointer is, and they count. A task fixed on its day
to which an arrow leads always shows "on" and its day. The wheel on a date moves it a day a notch, up for later: on
the start the task moves with its length kept, on the end and on the days of the dimension line its end moves. The
turns are one operation, stored when the wheel has rested, dropped by Escape, and the chart is not zoomed.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps

DIMENSION_LINE: str = 'div[class~="z-[3]"] > svg[class~="h-px"]'
# Writes down, from now on, whether a dimension line was drawn in any frame.
WATCH_JS: str = """
() => {
  window.__dimensions = 0;
  const watch = () => {
    if (document.querySelector('div[class~="z-[3]"] > svg[class~="h-px"]')) window.__dimensions += 1;
    if (!window.__stopped) requestAnimationFrame(watch);
  };
  window.__stopped = false;
  requestAnimationFrame(watch);
}
"""


def read_bars_of(page: pw.Page, *names: str) -> t.Dict[str, chart.Task]:
    drawn: t.Dict[str, chart.Task] = chart.read_bars(page)
    return {name: drawn[name] for name in names}


def read_stored_of(
    check: steps.Check, project: ins.Project, *names: str
) -> t.Dict[str, chart.Task]:
    stored: t.Dict[str, chart.Task] = chart.read_stored(check.instance, project)[0]
    return {name: stored[name] for name in names}


def read_shown(
    page: pw.Page,
) -> t.Tuple[t.Dict[str, t.List[str]], t.Optional[t.List[t.Any]]]:
    return chart.read_dates_beside(page), chart.read_dimension(page)


def check_turns(check: steps.Check, page: pw.Page, project: ins.Project) -> None:
    writes: t.List[str] = browser.record_writes(page)
    px_per_day: float = chart.get_px_per_day(page)
    start: browser.Point = chart.get_bar_point(page, "first")
    page.mouse.move(*start)
    page.locator(DIMENSION_LINE).wait_for()
    start_date: pw.Locator = page.locator(
        'div[class~="z-[3]"] [class~="text-11"]'
    ).filter(has_text=chart.format_day(chart.day(1)))
    point: browser.Point = browser.get_point(start_date)
    chart.turn_wheel(page, point, 1)
    check.expect(
        "a notch up on the date of its start: the task starts a day later with its length kept, the task that "
        "follows it moves with it, the date under the pointer says so, the chart is not zoomed and nothing is sent",
        lambda: (
            read_bars_of(page, "first", "second"),
            chart.read_text_at(page, point),
            chart.get_px_per_day(page),
            browser.read_writes(page, writes),
        ),
        (
            {
                "first": (chart.day(2), chart.day(4), True),
                "second": (chart.day(7), chart.day(7), False),
            },
            chart.format_day(chart.day(2)),
            px_per_day,
            [],
        ),
    )
    check.expect(
        "the wheel has rested: that is stored, in one request",
        lambda: (
            read_stored_of(check, project, "first", "second"),
            len(browser.read_writes(page, writes)),
        ),
        (
            {
                "first": (chart.day(2), chart.day(4), True),
                "second": (chart.day(7), chart.day(7), False),
            },
            1,
        ),
    )
    end_date: pw.Locator = page.locator(
        'div[class~="z-[3]"] [class~="text-11"]'
    ).filter(has_text=chart.format_day(chart.day(4)))
    point = browser.get_point(end_date)
    chart.turn_wheel(page, point, 2)
    check.expect(
        "two notches up on the date of its end: it ends two days later and starts where it did, the next task "
        "moves with its end, and the days of the dimension line count",
        lambda: (read_bars_of(page, "first", "second"), chart.read_dimension(page)[1]),
        (
            {
                "first": (chart.day(2), chart.day(6), True),
                "second": (chart.day(9), chart.day(9), False),
            },
            "5 d",
        ),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape puts it back",
        lambda: chart.read_bars(page)["first"],
        (chart.day(2), chart.day(4), True),
    )
    days: pw.Locator = page.locator('div[class~="z-[3]"] > div[class~="text-11"]')
    point = browser.get_point(days)
    chart.turn_wheel(page, point, -5)
    check.expect(
        "notches down on the days of the dimension line: the task is shorter at its end, and stops at one day",
        lambda: (chart.read_bars(page)["first"], chart.read_dimension(page)[1]),
        ((chart.day(2), chart.day(2), True), "1 d"),
    )
    page.keyboard.press("Escape")


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(1), "target_date": chart.day(3)},
            {
                "name": "second",
                "start_date": chart.day(6),
                "target_date": chart.day(6),
                "is_start_fixed": False,
            },
            {"name": "third", "start_date": chart.day(3), "target_date": chart.day(5)},
            {"name": "fourth", "start_date": chart.day(2), "target_date": chart.day(6)},
            {"name": "fixed", "start_date": chart.day(8), "target_date": chart.day(9)},
        ],
        [("first", "second", "end-start", 2), ("third", "fixed", "end-start", 0)],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=2)
    resting: t.Dict[str, t.List[str]] = {
        "fixed": [f"on {chart.format_day(chart.day(8))}"]
    }
    page.mouse.move(*chart.find_empty_point(page))
    check.expect(
        "with the pointer on no bar, the fixed task to which an arrow leads shows on and its day, and nothing else "
        "shows a date or a dimension line",
        lambda: read_shown(page),
        (resting, None),
    )

    page.mouse.move(*chart.get_bar_point(page, "third"))
    check.expect(
        "the pointer rests on a bar: a moment later its start and its end stand beside it, and the dimension line "
        "over it is as wide as the bar and says the days it lasts",
        lambda: read_shown(page),
        (
            {
                **resting,
                "third": [
                    chart.format_day(chart.day(3)),
                    chart.format_day(chart.day(5)),
                ],
            },
            ["third", "3 d", round(3 * chart.get_px_per_day(page))],
        ),
    )
    page.mouse.move(*chart.find_empty_point(page))
    check.expect(
        "the pointer leaves the bar: a moment later they are gone",
        lambda: read_shown(page),
        (resting, None),
    )

    page.evaluate(WATCH_JS)
    bottom: browser.Point = chart.get_bar_point(page, "fixed")
    top: browser.Point = chart.get_bar_point(page, "first")
    page.mouse.move(top[0] + 30, top[1] - 30)
    page.mouse.move(top[0] + 30, bottom[1] + 30, steps=10)
    page.mouse.move(*chart.find_empty_point(page), steps=4)
    check.expect(
        "the pointer sweeps down across the bars: no bar showed a dimension line in any frame",
        lambda: page.evaluate("window.__stopped = true, window.__dimensions"),
        0,
    )

    held: browser.Point = chart.get_bar_point(page, "fourth")
    chart.drag_bar(page, "fourth", 2)
    # straight up, so that the bar stays on its new days, onto the bar of another task
    page.mouse.move(
        held[0] + 2 * chart.get_px_per_day(page),
        chart.get_line_y(page, "third"),
        steps=6,
    )
    check.expect(
        "a bar is dragged and the pointer goes onto another bar: the dragged bar shows its dates where it is held, "
        "and the other bar none of its own",
        lambda: read_shown(page),
        (
            {
                **resting,
                "fourth": [
                    chart.format_day(chart.day(4)),
                    chart.format_day(chart.day(8)),
                ],
            },
            ["fourth", "5 d", round(5 * chart.get_px_per_day(page))],
        ),
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    check_turns(check, page, project)
    page.context.close()
