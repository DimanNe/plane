"""
A drop into another group than the one the drag began in changes the value of the work item and keeps its parent:
between lines, at the top level and on the header of the group alike. The work item then goes under its parent,
whose line is marked for it where the group shows that parent already, and which the group shows with it after the
drop where it did not. Only a drop on a line gives it another parent: that line, also the dimmed line of a parent
from another group.
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
            {"name": "grandparent", "state": "Backlog"},
            {"name": "parent", "state": "Todo", "parent": "grandparent"},
            {"name": "sibling", "state": "In Progress", "parent": "grandparent"},
            {"name": "top", "state": "In Progress"},
            {"name": "other parent", "state": "In Progress"},
            {"name": "loose", "state": "Todo"},
            {"name": "child of other", "state": "Todo", "parent": "other parent"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)

    ll.carry_line(page, "parent")
    ll.hold_over(page, ll.group_header(page, "In Progress"), down=0.5)
    check.expect(
        "over the header of a group that shows its parent: the line of the parent is marked",
        lambda: read_marks(page),
        [{"into": "grandparent"}],
    )
    ll.hold_over(page, ll.line(page, "top"), down=0.15)
    check.expect(
        "at the top level of that group too: the line of the parent, not a place",
        lambda: read_marks(page),
        [{"into": "grandparent"}],
    )
    page.mouse.up()
    check.expect(
        "dropped there, it takes the state, keeps its parent and stands under it",
        lambda: (
            read_parent_and_state(check, project, "parent"),
            ["In Progress", 1, "parent"] in ll.read_lines(page),
        ),
        (("grandparent", "In Progress"), True),
    )

    ll.carry_line(page, "child of other")
    ll.hold_over(page, ll.group_header(page, "Backlog"), down=0.5)
    check.expect(
        "over the header of a group that does not show its parent: the group is marked, with the line at its end",
        lambda: read_marks(page),
        [{"line": "at the end of", "at": "Backlog"}, {"group": "Backlog"}],
    )
    page.mouse.up()
    check.expect(
        "dropped there, it takes the state and keeps its parent, which the group now shows above it, dimmed",
        lambda: (
            read_parent_and_state(check, project, "child of other"),
            [line for line in ll.read_lines(page) if line[0] == "Backlog"],
            ["Backlog", "other parent"] in ll.read_lines_in_another_group(page),
        ),
        (
            ("other parent", "Backlog"),
            [
                ["Backlog", 0, "grandparent"],
                ["Backlog", 0, "other parent"],
                ["Backlog", 1, "child of other"],
            ],
            True,
        ),
    )

    ll.carry_line(page, "loose")
    ll.hold_over(page, ll.line_in_group(page, "In Progress", "other parent"), down=0.5)
    check.expect(
        "over the middle of a line of another group: that line is marked as the one that takes it in",
        lambda: read_marks(page),
        [{"into": "other parent"}],
    )
    page.mouse.up()
    check.expect(
        "dropped there, it is that line's sub-work item and takes the state",
        lambda: read_parent_and_state(check, project, "loose"),
        ("other parent", "In Progress"),
    )

    ll.drop_on(
        page,
        ll.line(page, "top"),
        ll.line_in_group(page, "Backlog", "other parent"),
        down=0.5,
    )
    check.expect(
        "dropped on the dimmed line of a parent in another group, it is that parent's sub-work item and takes "
        "the state of the group",
        lambda: read_parent_and_state(check, project, "top"),
        ("other parent", "Backlog"),
    )
    page.context.close()
