"""
A drag of empty space on the timeline's chart moves the time and the lines by the distance of the drag, and leaves
the scale. Today brings now back to the middle of the chart.
"""

import playwright.sync_api as pw

import browser
import chart
import steps
import timeline_scale as ts


def run(check: steps.Check) -> None:
    page: pw.Page = ts.open_timeline_of_plan(check)
    box: pw.FloatRect = ts.get_chart_box(page)
    left: float = box["x"] + 360
    empty: browser.Point = chart.find_empty_point(page)
    day: float = chart.read_day_at(page, empty[0])
    px_per_day: float = chart.get_px_per_day(page)
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
            page.evaluate(ts.NOW_JS) - (left + (box["x"] + box["width"] - left) / 2)
        )
        in range(-12, 13),
        True,
    )
    page.context.close()
