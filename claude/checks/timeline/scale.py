"""
The timeline opens with every bar and today in view, today marked in the header and by the line of now. The wheel
over the chart zooms it around the day under the pointer, up to zoom in; over the list the wheel scrolls the lines
and leaves the scale. The checks named after this one find the units of the header and the drag of empty space.
"""

import datetime as dt

import playwright.sync_api as pw

import browser
import chart
import steps
import timeline_scale as ts


def read_drift(page: pw.Page, point: browser.Point, day: float) -> int:
    """How many whole pixels the day that was under a point has moved away from it."""
    return int((chart.read_day_at(page, point[0]) - day) * chart.get_px_per_day(page))


def run(check: steps.Check) -> None:
    page: pw.Page = ts.open_timeline_of_plan(check)
    box: pw.FloatRect = ts.get_chart_box(page)
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
            int(chart.read_day_at(page, page.evaluate(ts.NOW_JS)))
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
    page.context.close()
