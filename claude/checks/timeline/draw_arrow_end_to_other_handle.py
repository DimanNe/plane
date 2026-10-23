"""
An end of an arrow taken to the other handle of its bar changes the arrow's kind: the tail of an arrow from an end
to a start taken to the start makes it start to start, its head taken to the end makes it end to end, each stored
on release in one request. Escape puts the arrow back and sends nothing, and a handle that does not take the end
refuses it, says why, and leaves the arrow as it was.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps


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
                "start_date": chart.day(8),
                "target_date": chart.day(8),
                "is_start_fixed": False,
            },
            {
                "name": "third",
                "start_date": chart.day(5),
                "target_date": chart.day(9),
                "is_start_fixed": False,
            },
            {"name": "fourth", "start_date": chart.day(2), "target_date": chart.day(4)},
        ],
        [
            ("first", "second", "end-start", 4),
            ("first", "third", "end-start", 1),
            ("fourth", "second", "end-end", 4),
            ("fourth", "third", "start-start", 3),
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=4)
    writes: t.List[str] = browser.record_writes(page)
    stored: t.Tuple[t.Dict[str, chart.Task], t.List[chart.Arrow]] = chart.read_stored(
        check.instance, project
    )
    chart.drag(
        page,
        chart.get_arrow_end_point(page, "first", "third", "tail"),
        chart.get_half_point(page, "first", "start"),
    )
    check.expect(
        "the tail of an arrow from an end to a start taken to the start of its bar: the arrow is drawn from start "
        "to start",
        lambda: ("first", "third", "start-start") in chart.read_arrows(page),
        True,
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    check.expect_stays(
        "after Escape it is as it was, and nothing is sent",
        lambda: (
            ("first", "third", "end-start") in chart.read_arrows(page),
            chart.read_stored(check.instance, project),
            browser.read_writes(page, writes),
        ),
        (True, stored, []),
    )
    chart.drag(
        page,
        chart.get_arrow_end_point(page, "first", "third", "tail"),
        chart.get_half_point(page, "first", "start"),
    )
    chart.let_go(page)
    check.expect(
        "let go there, it is stored from start to start, in one request",
        lambda: (
            [
                arrow[:3]
                for arrow in chart.read_stored(check.instance, project)[1]
                if arrow[:2] == ("first", "third")
            ],
            len(browser.read_writes(page, writes)),
        ),
        ([("first", "third", "start-start")], 1),
    )
    chart.drag(
        page,
        chart.get_arrow_end_point(page, "first", "second", "head"),
        chart.get_half_point(page, "second", "end"),
    )
    chart.let_go(page)
    check.expect(
        "the head of an arrow from an end to a start taken to the end of its bar: it is stored from end to end",
        lambda: [
            arrow[:3]
            for arrow in chart.read_stored(check.instance, project)[1]
            if arrow[:2] == ("first", "second")
        ],
        [("first", "second", "end-end")],
    )
    stored = chart.read_stored(check.instance, project)
    writes.clear()
    chart.drag(
        page,
        chart.get_arrow_end_point(page, "first", "third", "head"),
        chart.get_half_point(page, "third", "end"),
    )
    check.expect(
        "the head of an arrow from a start to a start held at the end of its bar: the handle refuses it and says "
        "why",
        lambda: (chart.read_marked_handles(page), chart.read_refusals(page)),
        ([["third", "end", "refuses"]], ["No arrow runs from a start to an end"]),
    )
    chart.let_go(page)
    check.expect_stays(
        "let go, the arrow stays as it was, and nothing is sent",
        lambda: (
            ("first", "third", "start-start") in chart.read_arrows(page),
            chart.read_stored(check.instance, project),
            browser.read_writes(page, writes),
        ),
        (True, stored, []),
    )
    page.context.close()
