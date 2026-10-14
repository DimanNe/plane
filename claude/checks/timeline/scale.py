"""
The timeline opens with every bar and today in view, today marked in the header and by the line of now. The wheel
over the chart zooms it around the day under the pointer, up to zoom in, and the header shows the units that fit
the scale, from days through weeks, months and quarters to years; over the list the wheel scrolls the lines and
leaves the scale. A drag of empty space moves the time and the lines by the distance of the drag. Today brings now
back to the middle of the chart.
"""

import datetime as dt
import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps

# The lower part of the header: the label of each interval and its width; and the line of now, where it stands.
HEADER_JS: str = chart.make_js(
    """
  const header = chart.firstElementChild.lastElementChild;
  return [...header.querySelectorAll(':scope > div.top-7')].map((cell) => [cell.textContent.trim(), cell.getBoundingClientRect().width]);"""
)
NOW_JS: str = chart.make_js(
    """
  const now = chart.querySelector('div[class~="z-[3]"] > div[class~="w-px"][class~="bg-accent-primary"]');
  return now.getBoundingClientRect().left;"""
)
MONTHS: t.Tuple[str, ...] = tuple(
    f"{dt.date(2000, month, 1):%b}" for month in range(1, 13)
)


def read_unit(page: pw.Page) -> str:
    """The unit of the lower part of the header, told by its labels: days and weeks are numbered by the day of the month
    they begin on, a day a step apart or seven."""
    labels: t.List[str] = [label for label, _ in page.evaluate(HEADER_JS)]
    if all(label.startswith("Q") for label in labels):
        return "quarter"
    if all(label.isdigit() and len(label) == 4 for label in labels):
        return "year"
    if all(label[:3] in MONTHS and not label[-1].isdigit() for label in labels):
        return "month"
    numbers: t.List[int] = [int(label.split()[-1]) for label in labels]
    steps_between: t.Set[int] = {
        (b - a) % 7 for a, b in zip(numbers, numbers[1:]) if b > a
    }
    return (
        "day"
        if steps_between == {1}
        else "week"
        if steps_between == {0}
        else f"unknown {labels}"
    )


def read_drift(page: pw.Page, point: browser.Point, day: float) -> int:
    """How many whole pixels the day that was under a point has moved away from it."""
    return int((chart.read_day_at(page, point[0]) - day) * chart.get_px_per_day(page))


def get_chart_box(page: pw.Page) -> pw.FloatRect:
    box: t.Optional[pw.FloatRect] = page.locator(
        ".vertical-scrollbar.isolate"
    ).bounding_box()
    assert box is not None
    return box


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [{"name": "first", "start_date": chart.day(-3), "target_date": chart.day(-1)}]
        + [{"name": f"line {number}"} for number in range(1, 25)]
        + [{"name": "last", "start_date": chart.day(6), "target_date": chart.day(9)}],
    )
    page: pw.Page = chart.open_timeline(check, account, project)
    box: pw.FloatRect = get_chart_box(page)
    left: float = box["x"] + 360
    check.expect(
        "the timeline opens with every bar and today in view, today marked in the header, the line of now on it",
        lambda: (
            left
            < chart.get_day_x(page, chart.day(-3))
            < chart.get_day_x(page, chart.day(9), 1)
            < box["x"] + box["width"],
            page.locator(
                '.vertical-scrollbar.isolate div.top-7 span[class~="bg-accent-primary"]'
            ).inner_text(),
            int(chart.read_day_at(page, page.evaluate(NOW_JS)))
            == (dt.date.today() - dt.date(1970, 1, 1)).days,
        ),
        (True, str(dt.date.today().day), True),
    )
    point: browser.Point = (left + 300, box["y"] + box["height"] - 60)
    day: float = chart.read_day_at(page, point[0])
    px_per_day: float = chart.get_px_per_day(page)
    chart.turn_wheel(page, point, 1)
    check.expect(
        "a notch up over the chart zooms it in, and the day under the pointer stays under it, to the pixel",
        lambda: (
            chart.get_px_per_day(page) > px_per_day,
            read_drift(page, point, day),
        ),
        (True, 0),
    )
    chart.turn_wheel(page, point, -3)
    check.expect(
        "three notches down zoom it out, around the same day",
        lambda: (
            chart.get_px_per_day(page) < px_per_day,
            read_drift(page, point, day),
        ),
        (True, 0),
    )
    scale: float = chart.read_px_per_day_at_rest(page)
    chart.turn_wheel(page, (box["x"] + 150, box["y"] + 300), -3)
    check.expect(
        "over the list the wheel scrolls the lines and leaves the scale",
        lambda: (
            page.locator(".vertical-scrollbar.isolate").evaluate(
                "(element) => element.scrollTop"
            )
            > 0,
            chart.get_px_per_day(page),
        ),
        (True, scale),
    )
    page.locator(".vertical-scrollbar.isolate").evaluate(
        "(element) => element.scrollTo(0, 0)"
    )

    chart.turn_wheel(page, point, 4)
    units: t.List[str] = [read_unit(page)]
    _: int
    for _ in range(40):
        chart.turn_wheel(page, point, -1)
        if read_unit(page) != units[-1]:
            units.append(read_unit(page))
    check.expect(
        "zoomed out notch by notch, the header shows days, then weeks, months, quarters and years",
        lambda: units,
        ["day", "week", "month", "quarter", "year"],
    )
    page.reload()
    page.locator(chart.LINE).first.wait_for()
    page.locator(".vertical-scrollbar.isolate div.top-7").first.wait_for()

    empty: browser.Point = chart.find_empty_point(page)
    day = chart.read_day_at(page, empty[0])
    px_per_day = chart.get_px_per_day(page)
    chart.drag(page, empty, (empty[0] - 174, empty[1] - 88))
    chart.let_go(page)
    check.expect(
        "a drag of empty space 174 px left and 88 px up moves the time and the lines that far, and leaves the scale",
        lambda: (
            round((chart.read_day_at(page, empty[0]) - day) * px_per_day),
            page.locator(".vertical-scrollbar.isolate").evaluate(
                "(element) => element.scrollTop"
            ),
            chart.get_px_per_day(page),
        ),
        (174, 88, px_per_day),
    )
    chart.drag(page, (left + 600, empty[1]), (left + 60, empty[1]))
    chart.let_go(page)
    chart.drag(page, (left + 600, empty[1]), (left + 60, empty[1]))
    chart.let_go(page)
    page.get_by_role("button", name="Today", exact=True).click()
    check.expect(
        "Today puts the line of now in the middle of the chart",
        lambda: round(
            page.evaluate(NOW_JS) - (left + (box["x"] + box["width"] - left) / 2)
        )
        in range(-12, 13),
        True,
    )
    page.context.close()
