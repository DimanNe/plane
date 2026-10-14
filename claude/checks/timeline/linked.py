"""
Tasks joined by linked arrows move as one body, whichever of them is moved, and an edge that a link holds takes the
other task with it; no move makes a link come apart, and none turns it into "in ≥ n d". A body that an arrow "in
≥ n d" leads into from outside goes later freely; earlier, that arrow gives its room and then its days, and stops
the move at "in ≥ 0 d", which it says while the bar is held. A task pushed later by an arrow takes the body it is
linked to along. Escape puts all of it back.
"""

import typing as t

import playwright.sync_api as pw

import chart
import instance as ins
import steps

Tasks: t.TypeAlias = t.Dict[str, chart.Task]


def read_tasks(
    page: pw.Page, check: steps.Check, project: ins.Project, names: t.Sequence[str]
) -> t.Tuple[Tasks, Tasks]:
    """Some tasks as the chart draws them and as the server has them."""
    drawn: Tasks = chart.read_bars(page)
    stored: Tasks = chart.read_stored(check.instance, project)[0]
    return {name: drawn[name] for name in names}, {name: stored[name] for name in names}


def make_tasks(*tasks: t.Tuple[str, int, int, bool]) -> Tasks:
    return {
        name: (chart.day(start), chart.day(end), is_fixed)
        for name, start, end, is_fixed in tasks
    }


def check_ends_linked(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "left", "start_date": chart.day(2), "target_date": chart.day(8)},
            {
                "name": "right",
                "start_date": chart.day(6),
                "target_date": chart.day(8),
                "is_start_fixed": False,
            },
        ],
        [("left", "right", "end-end", None)],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=1)
    way: str
    name: str
    part: str
    days: int
    left: t.Tuple[int, int]
    right: t.Tuple[int, int]
    for way, name, part, days, left, right in (
        (
            "left is moved two days later: right goes with it",
            "left",
            "middle",
            2,
            (4, 10),
            (8, 10),
        ),
        (
            "left is made three days longer at its end: the end of right goes with it",
            "left",
            "end",
            3,
            (4, 13),
            (11, 13),
        ),
        (
            "left is made a day longer at its start: its end stays, and so does right",
            "left",
            "start",
            -1,
            (3, 13),
            (11, 13),
        ),
        (
            "right is moved four days earlier: left goes with it as a whole",
            "right",
            "middle",
            -4,
            (-1, 9),
            (7, 9),
        ),
        (
            "right is made two days longer at its end, the edge the link holds: left goes with it as a whole",
            "right",
            "end",
            2,
            (1, 11),
            (7, 11),
        ),
        (
            "right is made a day shorter at its start: its end stays, and so does left",
            "right",
            "start",
            1,
            (1, 11),
            (8, 11),
        ),
    ):
        expected: Tasks = make_tasks(("left", *left, True), ("right", *right, False))
        chart.drag_bar(page, name, days, part)
        check.expect(
            f"the ends of two tasks linked, {way}, while the bar is held; the arrow says linked",
            lambda: (
                read_tasks(page, check, project, ["left", "right"])[0],
                chart.read_texts(page),
            ),
            (expected, {("left", "right"): "linked"}),
        )
        chart.let_go(page)
        check.expect(
            "  and so it is stored, the arrow still linked",
            lambda: chart.read_stored(check.instance, project),
            (expected, [("left", "right", "end-end", None)]),
        )
    page.context.close()


def check_body(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "pusher", "start_date": chart.day(0), "target_date": chart.day(1)},
            {"name": "holder", "start_date": chart.day(3), "target_date": chart.day(6)},
            {
                "name": "head",
                "start_date": chart.day(7),
                "target_date": chart.day(8),
                "is_start_fixed": False,
            },
            {
                "name": "tail",
                "start_date": chart.day(7),
                "target_date": chart.day(7),
                "is_start_fixed": False,
            },
        ],
        [
            ("pusher", "head", "end-start", 3),
            ("holder", "head", "end-start", None),
            ("holder", "tail", "end-start", None),
        ],
    )
    names: t.List[str] = ["pusher", "holder", "head", "tail"]
    page: pw.Page = chart.open_timeline(check, account, project, arrows=3)
    check.expect(
        "a body of three tasks held by a fixed one, with an arrow in ≥ 3 d into it from outside that has two days of "
        "room",
        lambda: (read_tasks(page, check, project, names)[0], chart.read_texts(page)),
        (
            make_tasks(
                ("pusher", 0, 1, True),
                ("holder", 3, 6, True),
                ("head", 7, 8, False),
                ("tail", 7, 7, False),
            ),
            {
                ("pusher", "head"): "in ≥ 3 d",
                ("holder", "head"): "linked",
                ("holder", "tail"): "linked",
            },
        ),
    )

    chart.drag_bar(page, "head", 2)
    chart.let_go(page)
    moved: Tasks = make_tasks(
        ("pusher", 0, 1, True),
        ("holder", 5, 8, True),
        ("head", 9, 10, False),
        ("tail", 9, 9, False),
    )
    check.expect(
        "a task of the body is moved two days later: the whole body goes, and the arrow from outside keeps its days",
        lambda: chart.read_stored(check.instance, project),
        (
            moved,
            [
                ("holder", "head", "end-start", None),
                ("holder", "tail", "end-start", None),
                ("pusher", "head", "end-start", 3),
            ],
        ),
    )
    chart.drag_bar(page, "tail", -2)
    chart.let_go(page)
    check.expect(
        "another task of it is moved two days earlier: the whole body is back",
        lambda: read_tasks(page, check, project, names),
        (
            make_tasks(
                ("pusher", 0, 1, True),
                ("holder", 3, 6, True),
                ("head", 7, 8, False),
                ("tail", 7, 7, False),
            ),
        )
        * 2,
    )

    chart.drag_bar(page, "pusher", 4)
    check.expect(
        "the task outside is held four days later, two more than the room: the body goes two days later with the "
        "task it leads to, and no arrow is red",
        lambda: (
            read_tasks(page, check, project, names)[0],
            [
                look
                for look in chart.read_arrow_looks(page).values()
                if look[0] == "danger"
            ],
        ),
        (
            make_tasks(
                ("pusher", 4, 5, True),
                ("holder", 5, 8, True),
                ("head", 9, 10, False),
                ("tail", 9, 9, False),
            ),
            [],
        ),
    )
    chart.let_go(page)
    pushed: Tasks = make_tasks(
        ("pusher", 4, 5, True),
        ("holder", 5, 8, True),
        ("head", 9, 10, False),
        ("tail", 9, 9, False),
    )
    check.expect(
        "  and so it is stored, every link still linked",
        lambda: chart.read_stored(check.instance, project),
        (
            pushed,
            [
                ("holder", "head", "end-start", None),
                ("holder", "tail", "end-start", None),
                ("pusher", "head", "end-start", 3),
            ],
        ),
    )

    chart.drag_bar(page, "holder", 2)
    page.keyboard.press("Escape")
    chart.let_go(page)
    check.expect(
        "the body is held later and Escape is pressed: everything is where it is stored",
        lambda: read_tasks(page, check, project, names),
        (pushed, pushed),
    )

    chart.drag_bar(page, "holder", -6)
    check.expect(
        "the body is held six days earlier: it stops after three, the days of the arrow from outside, which says "
        "in ≥ 0 d and that it stops the move",
        lambda: (
            read_tasks(page, check, project, names)[0],
            chart.read_texts(page).get(("pusher", "head")),
            chart.read_arrow_looks(page)[("pusher", "head")],
        ),
        (
            make_tasks(
                ("pusher", 4, 5, True),
                ("holder", 2, 5, True),
                ("head", 6, 7, False),
                ("tail", 6, 6, False),
            ),
            "in ≥ 0 d",
            ("stopping", "stopping"),
        ),
    )
    chart.let_go(page)
    check.expect(
        "  let go, it is stored there, the arrow from outside in ≥ 0 d",
        lambda: chart.read_stored(check.instance, project),
        (
            make_tasks(
                ("pusher", 4, 5, True),
                ("holder", 2, 5, True),
                ("head", 6, 7, False),
                ("tail", 6, 6, False),
            ),
            [
                ("holder", "head", "end-start", None),
                ("holder", "tail", "end-start", None),
                ("pusher", "head", "end-start", 0),
            ],
        ),
    )
    page.context.close()


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    check_ends_linked(check, account)
    check_body(check, account)
