"""
A handle that does not take an arrow drawn to it is marked red under the pointer and a text says why, and the plan
is drawn as it was: an arrow from a start to an end, to the same task, between tasks that are connected, and one
that would close a loop. Let go, nothing is stored and the text is gone.
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
    drawn: t.Tuple[t.Dict[str, chart.Task], t.List[chart.DrawnArrow]] = chart.read_plan(
        page
    )
    way: str
    source: t.Tuple[str, str]
    target: t.Tuple[str, str]
    said: str
    for way, source, target, said in (
        (
            "from a start to an end",
            ("first", "start"),
            ("fourth", "end"),
            "No arrow runs from a start to an end",
        ),
        (
            "to the same task",
            ("first", "start"),
            ("first", "end"),
            "An arrow goes from one task to another",
        ),
        (
            "between tasks that are connected",
            ("first", "end"),
            ("third", "start"),
            "These tasks are connected already",
        ),
        (
            "that closes a loop",
            ("third", "end"),
            ("first", "start"),
            "This arrow would close a loop",
        ),
    ):
        chart.draw_arrow(
            page,
            chart.get_handle_point(page, *source),
            chart.get_half_point(page, *target),
        )
        check.expect(
            f"an arrow {way}: the handle under the pointer is marked red, a text says why, and the plan is drawn "
            f"as it was",
            lambda: (
                chart.read_marked_handles(page),
                chart.read_refusals(page),
                chart.read_plan(page),
            ),
            ([[target[0], target[1], "refuses"]], [said], drawn),
        )
        chart.let_go(page)
        check.expect_stays(
            f"an arrow {way}, let go: nothing is stored and the text is gone",
            lambda: (
                chart.read_stored(check.instance, project),
                chart.read_refusals(page),
                browser.read_writes(page, writes),
            ),
            (stored, [], []),
        )
    page.context.close()
