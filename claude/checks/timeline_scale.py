"""
What the checks of the scale of the timeline need: timeline/scale and the checks named after it.
"""

import typing as t

import playwright.sync_api as pw

import chart
import instance as ins
import steps

# The line of now, where it stands.
NOW_JS: str = chart.make_js(
    """
  const now = chart.querySelector('div[class~="z-[3]"] > div[class~="w-px"][class~="bg-accent-primary"]');
  return now.getBoundingClientRect().left;"""
)


def open_timeline_of_plan(check: steps.Check) -> pw.Page:
    """The timeline of a plan with a bar from three days before today to yesterday and one from six to nine days
    after today, and 24 lines without dates between them, so that the lines can scroll."""
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [{"name": "first", "start_date": chart.day(-3), "target_date": chart.day(-1)}]
        + [{"name": f"line {number}"} for number in range(1, 25)]
        + [{"name": "last", "start_date": chart.day(6), "target_date": chart.day(9)}],
    )
    return chart.open_timeline(check, account, project)


def get_chart_box(page: pw.Page) -> pw.FloatRect:
    box: t.Optional[pw.FloatRect] = page.locator(
        ".vertical-scrollbar.isolate"
    ).bounding_box()
    assert box is not None
    return box
