"""
A line dragged to another group takes the lines under it along. In a list grouped by something that a work item
has one of, such as its state or its priority, every work item under the line gets the new value too, at every depth
and also where its line is folded. A sub-work item that stands in another group keeps its value, and so does a
parent that the group shows only for the structure. Where a work item can have several, as with labels, only the
dragged line changes.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def read_stored(
    check: steps.Check, project: ins.Project, field: str
) -> t.Dict[str, t.Any]:
    """A field of every work item, as the server has stored it, by name."""
    return {
        name: item[field]
        for name, item in ins.read_work_items(check.instance, project).items()
    }


def check_state(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "parent", "state": "Todo"},
            {"name": "child", "state": "Todo", "parent": "parent"},
            {"name": "grandchild", "state": "Todo", "parent": "child"},
            {"name": "done child", "state": "Done", "parent": "parent"},
            {"name": "other", "state": "Todo"},
        ],
    )
    names: t.Dict[str, str] = {
        state_id: state for state, state_id in project.states.items()
    }
    page: pw.Page = ll.open_list(check, account, project)
    ll.select_line(page, "child")
    page.keyboard.press("ArrowLeft")
    ll.drop_on(
        page, ll.line(page, "parent"), ll.group_header(page, "In Progress"), down=0.5
    )
    check.expect(
        "grouped by state: the work items under the dragged line get its new state, also under a folded line; one "
        "in another group keeps its own",
        lambda: {
            name: names[state]
            for name, state in read_stored(check, project, "state").items()
        },
        {
            "parent": "In Progress",
            "child": "In Progress",
            "grandchild": "In Progress",
            "done child": "Done",
            "other": "Todo",
        },
    )
    # the drag selected the dragged line, as the pointer moved onto it; the folded one is selected again to unfold it
    ll.select_line(page, "child")
    page.keyboard.press("ArrowRight")
    check.expect(
        "they stand under it in the new group",
        lambda: [line for line in ll.read_lines(page) if line[0] == "In Progress"],
        [
            ["In Progress", 0, "parent"],
            ["In Progress", 1, "child"],
            ["In Progress", 2, "grandchild"],
        ],
    )
    page.context.close()


def check_priority(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "parent", "priority": "low"},
            {"name": "child", "priority": "low", "parent": "parent"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by="priority")
    ll.drop_on(page, ll.line(page, "parent"), ll.group_header(page, "High"), down=0.5)
    check.expect(
        "grouped by priority: the sub-work item gets the new priority too",
        lambda: read_stored(check, project, "priority"),
        {"parent": "high", "child": "high"},
    )
    page.context.close()


def check_labels(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    labels: t.Dict[str, str] = {
        name: ins.call_api(
            check.instance,
            "POST",
            f"/projects/{project.id}/labels/",
            {"name": name, "color": "#3f76ff"},
        )["id"]
        for name in ("red", "blue")
    }
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "parent", "labels": [labels["red"]]},
            {"name": "child", "labels": [labels["red"]], "parent": "parent"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by="labels")
    ll.drop_on(page, ll.line(page, "parent"), ll.group_header(page, "blue"), down=0.5)
    check.expect(
        "grouped by labels, which a work item can have several of: only the dragged line changes",
        lambda: read_stored(check, project, "labels"),
        {"parent": [labels["blue"]], "child": [labels["red"]]},
    )
    page.context.close()


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    check_state(check, account)
    check_priority(check, account)
    check_labels(check, account)
