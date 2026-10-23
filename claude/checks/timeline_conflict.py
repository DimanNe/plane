"""
The conflict that the timeline/conflict* checks look at, and how they read it.
"""

import datetime as dt
import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps


def write_day(offset: int) -> str:
    """A day as the card writes it."""
    date: dt.date = dt.date.fromisoformat(chart.day(offset))
    return f"{date:%b} {date.day}"


def open_conflict(
    check: steps.Check, account: ins.Account
) -> t.Tuple[ins.Project, pw.Page]:
    """A task that follows another by a day, and a task fixed two days earlier than the arrow from it asks."""
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(0), "target_date": chart.day(1)},
            {
                "name": "middle",
                "start_date": chart.day(3),
                "target_date": chart.day(4),
                "is_start_fixed": False,
            },
            {"name": "late", "start_date": chart.day(5), "target_date": chart.day(7)},
        ],
        [("first", "middle", "end-start", 1), ("middle", "late", "end-start", 2)],
    )
    return project, chart.open_timeline(check, account, project, arrows=2)


def read_red(page: pw.Page) -> t.Tuple[t.List[t.Tuple[str, str]], t.List[str]]:
    """The arrows drawn red, and the tasks ringed red."""
    return (
        sorted(
            arrow
            for arrow, (colour, _) in chart.read_arrow_looks(page).items()
            if colour == "danger"
        ),
        chart.read_ringed(page, "danger"),
    )


def take_way_out(
    check: steps.Check, account: ins.Account, way: str
) -> t.Tuple[ins.Project, pw.Page, t.List[str]]:
    """The conflict opened again, and a way out of its card clicked; the requests the click sent."""
    project: ins.Project
    page: pw.Page
    project, page = open_conflict(check, account)
    # the pointer on the conflict's text, which the card stands by, once the text has found its place
    page.locator('div[class~="z-[3]"] [class~="text-11"]').filter(
        has_text="too early"
    ).first.hover()
    page.locator(chart.CARD).get_by_role("button", name=way).wait_for()
    writes: t.List[str] = browser.record_writes(page)
    page.locator(chart.CARD).get_by_role("button", name=way).click()
    return project, page, writes
