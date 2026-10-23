"""
While a line of the list is dragged, what is drawn says what a drop there does, and the drop does it: a thick
line between two lines on the level the work item lands on, the line that takes it in as a sub-work item, the
group it goes to. Where a drop does nothing, nothing is drawn. The line between two lines is drawn in every
order of the list.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

Mark: t.TypeAlias = t.Dict[str, t.Any]
ITEMS: t.List[ins.JSONObject] = [
    {"name": "b one", "state": "Backlog"},
    {"name": "b two", "state": "Backlog"},
    {"name": "b three", "state": "Backlog"},
    {"name": "t parent", "state": "Todo"},
    {"name": "t child one", "state": "Todo", "parent": "t parent"},
    {"name": "t child two", "state": "Todo", "parent": "t parent"},
    {"name": "t other", "state": "Todo"},
]


def make_line_mark(side: str, at: str, left: float, right: float) -> Mark:
    """The thick line as it has to be drawn: four pixels, not see-through, between these ends."""
    return {
        "line": side,
        "at": at,
        "from": round(left),
        "to": round(right),
        "thick": 4,
        "solid": True,
    }


def read_stored(
    check: steps.Check, project: ins.Project
) -> t.Dict[str, t.List[t.Tuple[t.Optional[str], str]]]:
    """Per state, the work items the server has in their manual order, each with its parent's name."""
    items: t.Dict[str, ins.JSONObject] = ins.read_work_items(check.instance, project)
    names: t.Dict[str, str] = {item["id"]: name for name, item in items.items()}
    stored: t.Dict[str, t.List[t.Tuple[t.Optional[str], str]]] = {}
    state: str
    state_id: str
    for state, state_id in project.states.items():
        of_state: t.List[ins.JSONObject] = sorted(
            (item for item in items.values() if item["state"] == state_id),
            key=lambda item: item["sort_order"],
        )
        if of_state:
            stored[state] = [
                (names.get(item["parent"]), item["name"]) for item in of_state
            ]
    return stored


def let_go_outside(page: pw.Page) -> None:
    browser.carry_to(page, browser.get_point(page.get_by_text("Work Items").first))
    page.mouse.up()


def check_what_is_drawn(
    check: steps.Check, page: pw.Page, project: ins.Project
) -> None:
    list_box: t.Optional[pw.FloatRect] = page.locator(
        ".vertical-scrollbar.scrollbar-lg"
    ).bounding_box()
    line_box: t.Optional[pw.FloatRect] = ll.line(page, "b three").bounding_box()
    child_text: t.Optional[pw.FloatRect] = (
        ll.line(page, "t child two")
        .get_by_text(f"{project.identifier}-", exact=False)
        .first.bounding_box()
    )
    assert list_box is not None and line_box is not None and child_text is not None
    left: float = list_box["x"]
    right: float = line_box["x"] + line_box["width"]

    ll.carry_line(page, "b one")
    ll.hold_over(page, ll.line(page, "b three"), down=0.15)
    check.expect(
        "over the upper part of a line: a thick line above it, from edge to edge of the list",
        lambda: ll.read_drop_marks(page),
        [make_line_mark("above", "b three", left, right)],
    )
    ll.hold_over(page, ll.line(page, "b three"), down=0.5)
    check.expect(
        "over its middle: the line is marked as the one that takes the work item in",
        lambda: ll.read_drop_marks(page),
        [{"into": "b three"}],
    )
    ll.hold_over(page, ll.line(page, "b three"), down=0.85)
    check.expect(
        "over its lower part: the thick line below it",
        lambda: ll.read_drop_marks(page),
        [make_line_mark("below", "b three", left, right)],
    )
    ll.hold_over(page, ll.line(page, "t child two"), down=0.15)
    check.expect(
        "among the sub-work items of another group the work item keeps its parent, here none: the group is "
        "marked, and the thick line stands at its end",
        lambda: ll.read_drop_marks(page),
        [make_line_mark("at the end of", "Todo", left, right), {"group": "Todo"}],
    )
    ll.hold_over(page, ll.group_header(page, "Todo"), down=0.5)
    check.expect(
        "over a group's header: the group is marked, and the thick line stands at its end",
        lambda: ll.read_drop_marks(page),
        [make_line_mark("at the end of", "Todo", left, right), {"group": "Todo"}],
    )
    ll.hold_over(page, ll.group_header(page, "In Progress"), down=0.5)
    check.expect(
        "over the header of a group without work items: the group is marked",
        lambda: ll.read_drop_marks(page),
        [{"group": "In Progress"}],
    )
    ll.hold_over(page, ll.line(page, "b one"), down=0.5)
    check.expect(
        "over the dragged line itself nothing is drawn",
        lambda: ll.read_drop_marks(page),
        [],
    )

    # from the middle of one line to the middle of the next, two pixels at a time
    upper: browser.Point = browser.get_point(ll.line(page, "b two"), across=0.3)
    lower: browser.Point = browser.get_point(ll.line(page, "b three"), across=0.3)
    heights: t.List[int] = list(range(round(upper[1]), round(lower[1]), 2))
    with_line: int = 0
    y: int
    for y in heights:
        browser.carry_to(page, (upper[0], y))
        marks: t.List[Mark] = ll.read_drop_marks(page)
        with_line += len(marks) == 1 and marks[0].get("line") in ("above", "below")
    check.expect_at_least(
        "the thick line holds for most of the way from the middle of a line to the middle of the next",
        round(with_line / len(heights), 2),
        0.7,
    )
    before: t.Any = read_stored(check, project)
    let_go_outside(page)
    check.expect_stays(
        "let go outside the list, the line stays where it was",
        lambda: (ll.read_drop_marks(page), read_stored(check, project)),
        ([], before),
    )
    ll.carry_line(page, "t other")
    ll.hold_over(page, ll.line(page, "t child two"), down=0.15)
    check.expect(
        "within its group, among sub-work items the thick line begins where their text begins",
        lambda: ll.read_drop_marks(page),
        [make_line_mark("above", "t child two", child_text["x"], right)],
    )
    let_go_outside(page)


def check_what_a_drop_does(
    check: steps.Check, page: pw.Page, project: ins.Project
) -> None:
    ll.drop_on(page, ll.line(page, "b one"), ll.line(page, "b three"), down=0.85)
    check.expect(
        "dropped on the lower part of a line, the work item stands after it, on the page and on the server",
        lambda: (ll.read_titles(page)[:3], read_stored(check, project)["Backlog"]),
        (
            ["b two", "b three", "b one"],
            [(None, "b two"), (None, "b three"), (None, "b one")],
        ),
    )
    ll.drop_on(page, ll.line(page, "b two"), ll.line(page, "b three"), down=0.5)
    check.expect(
        "dropped on the middle of a line, it is that line's sub-work item",
        lambda: (ll.read_lines(page)[:3], read_stored(check, project)["Backlog"]),
        (
            [
                ["Backlog", 0, "b three"],
                ["Backlog", 1, "b two"],
                ["Backlog", 0, "b one"],
            ],
            [(None, "b three"), (None, "b one"), ("b three", "b two")],
        ),
    )
    ll.drop_on(page, ll.line(page, "b one"), ll.group_header(page, "Todo"), down=0.5)
    check.expect(
        "dropped on a group's header, it is the last line of that group and has its state",
        lambda: (ll.read_lines(page)[2:], read_stored(check, project)["Todo"][-1]),
        (
            [
                ["Todo", 0, "t parent"],
                ["Todo", 1, "t child one"],
                ["Todo", 1, "t child two"],
                ["Todo", 0, "t other"],
                ["Todo", 0, "b one"],
            ],
            (None, "b one"),
        ),
    )
    ll.drop_on(page, ll.line(page, "t other"), ll.line(page, "t child two"), down=0.15)
    check.expect(
        "dropped between two sub-work items, it is a sub-work item of their parent at that place",
        lambda: (
            ll.read_lines(page)[2:],
            [
                name
                for parent, name in read_stored(check, project)["Todo"]
                if parent == "t parent"
            ],
        ),
        (
            [
                ["Todo", 0, "t parent"],
                ["Todo", 1, "t child one"],
                ["Todo", 1, "t other"],
                ["Todo", 1, "t child two"],
                ["Todo", 0, "b one"],
            ],
            ["t child one", "t other", "t child two"],
        ),
    )
    ll.drop_on(
        page,
        ll.line(page, "t child one"),
        ll.group_header(page, "In Progress"),
        down=0.5,
    )
    check.expect(
        "a sub-work item dropped on the header of another group takes that state, keeps its parent and stands "
        "under it there",
        lambda: (
            ll.read_lines(page)[-2:],
            read_stored(check, project).get("In Progress"),
        ),
        (
            [["In Progress", 0, "t parent"], ["In Progress", 1, "t child one"]],
            [("t parent", "t child one")],
        ),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, ITEMS)
    page: pw.Page = ll.open_list(check, account, project)
    check_what_is_drawn(check, page, project)
    check_what_a_drop_does(check, page, project)
    page.context.close()

    project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, ITEMS)
    page = ll.open_list(check, account, project, order_by="-created_at")
    ll.carry_line(page, "b one")
    ll.hold_over(page, ll.line(page, "t other"), down=0.15)
    check.expect(
        "newest first: the thick line is drawn between two lines as in the manual order",
        lambda: [
            (mark.get("line"), mark.get("at")) for mark in ll.read_drop_marks(page)
        ],
        [("above", "t other")],
    )
    ll.hold_over(page, ll.line(page, "t other"), down=0.5)
    page.mouse.up()
    check.expect(
        "newest first: dropped on the middle of a line, it is that line's sub-work item in that state",
        lambda: (
            ["Todo", 1, "b one"] in ll.read_lines(page),
            ("t other", "b one") in read_stored(check, project)["Todo"],
        ),
        (True, True),
    )
    page.context.close()
