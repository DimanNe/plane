"""
A bar dragged along the time moves its task by whole days, and an edge dragged changes its start or its end. The
chart follows the pointer and nothing is stored until the button is let go, which stores the change in one
request. Escape during the drag puts everything back and stores nothing.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps


def read_moved(
    check: steps.Check, project: ins.Project, page: pw.Page
) -> t.Tuple[chart.Task, chart.Task]:
    """The task "moved" as the chart draws it and as the server has it."""
    return (
        chart.read_bars(page)["moved"],
        chart.read_stored(check.instance, project)[0]["moved"],
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "moved", "start_date": chart.day(2), "target_date": chart.day(4)},
            {"name": "beside", "start_date": chart.day(1), "target_date": chart.day(8)},
            {"name": "not placed"},
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project)
    check.expect(
        "the chart draws every task on its stored days, fixed, and no bar for a task without dates",
        lambda: chart.read_bars(page),
        {
            "moved": (chart.day(2), chart.day(4), True),
            "beside": (chart.day(1), chart.day(8), True),
            "not placed": (None, None, None),
        },
    )
    writes: t.List[str] = browser.record_writes(page)

    chart.drag_bar(page, "moved", 3)
    check.expect(
        "a bar held three days later stands there while nothing is sent",
        lambda: (read_moved(check, project, page), browser.read_writes(page, writes)),
        (((chart.day(5), chart.day(7), True), (chart.day(2), chart.day(4), True)), []),
    )
    chart.let_go(page)
    check.expect(
        "let go, the task is stored three days later, as it stands, in one request",
        lambda: (
            read_moved(check, project, page),
            len(browser.read_writes(page, writes)),
        ),
        (((chart.day(5), chart.day(7), True), (chart.day(5), chart.day(7), True)), 1),
    )

    writes.clear()
    chart.drag_bar(page, "moved", -2)
    check.expect(
        "held two days earlier, it stands there",
        lambda: chart.read_bars(page)["moved"],
        (chart.day(3), chart.day(5), True),
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    check.expect_stays(
        "Escape puts the bar back on its stored days and nothing is sent",
        lambda: (read_moved(check, project, page), browser.read_writes(page, writes)),
        (((chart.day(5), chart.day(7), True), (chart.day(5), chart.day(7), True)), []),
    )

    start: browser.Point = chart.get_bar_point(page, "moved")
    chart.drag(page, start, (start[0] + 0.4 * chart.get_px_per_day(page), start[1]))
    chart.let_go(page)
    check.expect_stays(
        "a bar let go less than half a day away stays on its days and nothing is sent",
        lambda: (read_moved(check, project, page), browser.read_writes(page, writes)),
        (((chart.day(5), chart.day(7), True), (chart.day(5), chart.day(7), True)), []),
    )

    chart.drag_bar(page, "moved", 2, part="end")
    chart.let_go(page)
    check.expect(
        "its end dragged two days later: it lasts two days longer",
        lambda: read_moved(check, project, page),
        ((chart.day(5), chart.day(9), True), (chart.day(5), chart.day(9), True)),
    )
    chart.drag_bar(page, "moved", -1, part="start")
    chart.let_go(page)
    check.expect(
        "its start dragged a day earlier: it starts a day earlier and ends on the same day",
        lambda: read_moved(check, project, page),
        ((chart.day(4), chart.day(9), True), (chart.day(4), chart.day(9), True)),
    )
    chart.drag_bar(page, "moved", 9, part="start")
    chart.let_go(page)
    check.expect(
        "its start dragged past its end: the task is one day long, on its last day",
        lambda: read_moved(check, project, page),
        ((chart.day(9), chart.day(9), True), (chart.day(9), chart.day(9), True)),
    )
    check.expect(
        "the three drags that stored something sent a request each",
        lambda: len(browser.read_writes(page, writes)),
        3,
    )

    start = chart.get_bar_point(page, "moved")
    px_per_day: float = chart.get_px_per_day(page)
    chart.drag(page, start, (start[0] - 2 * px_per_day, start[1] + 50))
    chart.let_go(page)
    check.expect(
        "a drag that begins along the time and also goes down moves the task, and its line stays in its place",
        lambda: (read_moved(check, project, page), chart.read_lines(page)),
        (
            ((chart.day(7), chart.day(7), True), (chart.day(7), chart.day(7), True)),
            ["moved", "beside", "not placed"],
        ),
    )
    check.expect(
        "the other task did not move",
        lambda: chart.read_stored(check.instance, project)[0]["beside"],
        (chart.day(1), chart.day(8), True),
    )
    page.context.close()
