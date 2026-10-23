"""
A drop within the group that the drag began in changes the structure and no value. On a line, also the dimmed line
of a parent from another group, the work item becomes that line's sub-work item. Above or below a line it becomes
a sibling of that line, under the line's parent. At the top level, and on the header of its own group, it has no
parent any more, also where its parent stood dimmed, in another group.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def read_marks(page: pw.Page) -> t.List[t.Dict[str, t.Any]]:
    """What is drawn for the carried line, without the geometry of a thick line."""
    return [
        {key: mark[key] for key in ("line", "at", "into", "group") if key in mark}
        for mark in ll.read_drop_marks(page)
    ]


def read_parent_and_state(
    check: steps.Check, project: ins.Project, name: str
) -> t.Tuple[t.Optional[str], str]:
    """The names of the parent and of the state of a work item, as the server has stored them."""
    items: t.Dict[str, ins.JSONObject] = ins.read_work_items(check.instance, project)
    names: t.Dict[str, str] = {item["id"]: name for name, item in items.items()}
    states: t.Dict[str, str] = {
        state_id: state for state, state_id in project.states.items()
    }
    return names.get(items[name]["parent"]), states[items[name]["state"]]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "outside parent", "state": "Backlog"},
            {"name": "a", "state": "Todo"},
            {"name": "b", "state": "Todo", "parent": "a"},
            {"name": "c", "state": "Todo", "parent": "a"},
            {"name": "d", "state": "Todo", "parent": "outside parent"},
            {"name": "f", "state": "Todo", "parent": "outside parent"},
            {"name": "e", "state": "Todo"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)

    ll.carry_line(page, "e")
    ll.hold_over(page, ll.line(page, "c"), down=0.5)
    check.expect(
        "over the middle of a line: that line is marked as the one that takes it in",
        lambda: read_marks(page),
        [{"into": "c"}],
    )
    page.mouse.up()
    check.expect(
        "dropped there, it is that line's sub-work item and keeps its state",
        lambda: (
            read_parent_and_state(check, project, "e"),
            ["Todo", 2, "e"] in ll.read_lines(page),
        ),
        (("c", "Todo"), True),
    )

    ll.carry_line(page, "e")
    ll.hold_over(page, ll.line(page, "b"), down=0.15)
    check.expect(
        "above a line: the thick line, on the level of that line",
        lambda: read_marks(page),
        [{"line": "above", "at": "b"}],
    )
    page.mouse.up()
    check.expect(
        "dropped there, it has the parent of that line",
        lambda: (
            read_parent_and_state(check, project, "e"),
            ["Todo", 1, "e"] in ll.read_lines(page),
        ),
        (("a", "Todo"), True),
    )

    ll.carry_line(page, "e")
    ll.hold_over(page, ll.line(page, "a"), down=0.15)
    check.expect(
        "above a line at the top level: the thick line there",
        lambda: read_marks(page),
        [{"line": "above", "at": "a"}],
    )
    page.mouse.up()
    check.expect(
        "dropped there, it has no parent any more",
        lambda: (
            read_parent_and_state(check, project, "e"),
            ["Todo", 0, "e"] in ll.read_lines(page),
        ),
        ((None, "Todo"), True),
    )

    ll.drop_on(page, ll.line(page, "d"), ll.line(page, "e"), down=0.15)
    check.expect(
        "a work item under a dimmed parent from another group, dropped at the top level, has no parent any more",
        lambda: (
            read_parent_and_state(check, project, "d"),
            ["Todo", 0, "d"] in ll.read_lines(page),
        ),
        ((None, "Todo"), True),
    )

    ll.drop_on(
        page,
        ll.line(page, "e"),
        ll.line_in_group(page, "Todo", "outside parent"),
        down=0.5,
    )
    check.expect(
        "dropped on the dimmed line of a parent from another group, it is that parent's sub-work item",
        lambda: read_parent_and_state(check, project, "e"),
        ("outside parent", "Todo"),
    )

    ll.carry_line(page, "b")
    ll.hold_over(page, ll.group_header(page, "Todo"), down=0.5)
    check.expect(
        "over the header of its own group: the group is marked, with the line at its end",
        lambda: read_marks(page),
        [{"line": "at the end of", "at": "Todo"}, {"group": "Todo"}],
    )
    page.mouse.up()
    check.expect(
        "dropped there, it has no parent any more and is the last line of the group",
        lambda: (
            read_parent_and_state(check, project, "b"),
            [line for line in ll.read_lines(page) if line[0] == "Todo"][-1],
        ),
        ((None, "Todo"), ["Todo", 0, "b"]),
    )
    page.context.close()
