"""
In a plan of tasks joined by arrows, the tasks and the arrows of the chain that decides when it ends are critical
and have a ring and the accent colour. A task whose end can go later before anything else changes has a tail as
long as those days, and a drag of its end that far changes nothing else; a day more moves the tasks after it.
While an operation is going on, an arrow whose days or length the operation has changed is green, and no other is.
"""

import typing as t

import playwright.sync_api as pw

import chart
import instance as ins
import steps


def read_colours(page: pw.Page) -> t.Dict[t.Tuple[str, str], str]:
    return {
        arrow: colour for arrow, (colour, _) in chart.read_arrow_looks(page).items()
    }


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(0), "target_date": chart.day(2)},
            {
                "name": "long",
                "start_date": chart.day(3),
                "target_date": chart.day(5),
                "is_start_fixed": False,
            },
            {
                "name": "short",
                "start_date": chart.day(3),
                "target_date": chart.day(3),
                "is_start_fixed": False,
            },
            {
                "name": "last",
                "start_date": chart.day(6),
                "target_date": chart.day(6),
                "is_start_fixed": False,
            },
        ],
        [
            ("first", "long", "end-start", 0),
            ("first", "short", "end-start", 0),
            ("long", "last", "end-start", 0),
            ("short", "last", "end-start", 0),
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=4)
    check.expect(
        "at rest the chain that decides the end is critical: its tasks are ringed and its arrows in the accent colour",
        lambda: (chart.read_ringed(page, "accent"), read_colours(page)),
        (
            ["first", "long", "last"],
            {
                ("first", "long"): "accent",
                ("long", "last"): "accent",
                ("first", "short"): "normal",
                ("short", "last"): "normal",
            },
        ),
    )
    check.expect(
        "the task whose end can go two days later before anything else changes has a tail of two days, and no "
        "other task has one",
        lambda: chart.read_tails(page),
        {"short": 2},
    )

    chart.drag_bar(page, "short", 2, part="end")
    check.expect(
        "its end held two days later: nothing else moves, and the arrow from it, whose length that changed, is "
        "green, and no other arrow",
        lambda: (
            chart.read_bars(page),
            [
                arrow
                for arrow, colour in read_colours(page).items()
                if colour == "changing"
            ],
        ),
        (
            {
                "first": (chart.day(0), chart.day(2), True),
                "long": (chart.day(3), chart.day(5), False),
                "short": (chart.day(3), chart.day(5), False),
                "last": (chart.day(6), chart.day(6), False),
            },
            [("short", "last")],
        ),
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    chart.drag_bar(page, "short", 3, part="end")
    check.expect(
        "its end held a day further than the tail: the task after it moves a day later",
        lambda: chart.read_bars(page)["last"],
        (chart.day(7), chart.day(7), False),
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    check.expect(
        "after Escape no arrow is green, and the tail is back",
        lambda: (
            [
                arrow
                for arrow, colour in read_colours(page).items()
                if colour == "changing"
            ],
            chart.read_tails(page),
        ),
        ([], {"short": 2}),
    )

    chart.drag_bar(page, "short", 2, part="end")
    chart.let_go(page)
    check.expect(
        "let go two days later: that is stored, nothing else changed, and the task has no tail any more",
        lambda: (
            chart.read_stored(check.instance, project)[0],
            chart.read_tails(page),
        ),
        (
            {
                "first": (chart.day(0), chart.day(2), True),
                "long": (chart.day(3), chart.day(5), False),
                "short": (chart.day(3), chart.day(5), False),
                "last": (chart.day(6), chart.day(6), False),
            },
            {},
        ),
    )
    page.context.close()
