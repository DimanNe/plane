"""
The wheel over the timeline's chart zooms it, and the header shows the units that fit the scale, from days through
weeks, months and quarters to years.
"""

import datetime as dt
import typing as t

import playwright.sync_api as pw

import browser
import chart
import steps
import timeline_scale as ts

# The lower part of the header: the label of each interval and its width.
HEADER_JS: str = chart.make_js(
    """
  const header = chart.firstElementChild.lastElementChild;
  return [...header.querySelectorAll(':scope > div.top-7')].map((cell) => [cell.textContent.trim(), cell.getBoundingClientRect().width]);"""
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


def run(check: steps.Check) -> None:
    page: pw.Page = ts.open_timeline_of_plan(check)
    box: pw.FloatRect = ts.get_chart_box(page)
    left: float = box["x"] + 360
    point: browser.Point = (left + 300, box["y"] + box["height"] - 60)
    # two notches above the scale the timeline opens with: a notch up, three down, then four up
    chart.turn_wheel(page, point, 1)
    chart.read_px_per_day_at_rest(page)
    chart.turn_wheel(page, point, -3)
    chart.read_px_per_day_at_rest(page)
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
    page.context.close()
