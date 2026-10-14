"""
The header of every group of the list has a "+" right after its count. It opens an input under the header;
Enter there stores a work item with what the group stands for and leaves the input open for the next one.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def read_state(check: steps.Check, project: ins.Project, name: str) -> t.Optional[str]:
    """The name of the state the server has stored for a work item; None while it is not stored."""
    states: t.Dict[str, str] = {
        state_id: state for state, state_id in project.states.items()
    }
    item: ins.JSONObject = ins.read_work_items(check.instance, project).get(name, {})
    return states.get(item.get("state"))


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "in backlog", "state": "Backlog"},
            {"name": "in todo", "state": "Todo"},
            {"name": "in progress", "state": "In Progress"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    check.expect(
        'every group has the "+", also a group without work items',
        lambda: ll.read_groups(page),
        [
            ["Backlog", 1, 1, True],
            ["Todo", 1, 1, True],
            ["In Progress", 1, 1, True],
            ["Done", 0, 0, True],
            ["Cancelled", 0, 0, True],
        ],
    )

    ll.plus_of_group(page, "Todo").click()
    check.expect(
        'the "+" opens an empty input right under the header of its group, with the caret in it',
        lambda: ll.read_input_of_group(page),
        ["Todo", "", True, True],
    )
    page.keyboard.type("added to todo")
    page.keyboard.press("Enter")
    check.expect(
        "Enter stores the work item in the state of the group",
        lambda: read_state(check, project, "added to todo"),
        "Todo",
    )
    check.expect(
        "the group shows and counts it, and the input is open and empty for the next one",
        lambda: (ll.read_groups(page)[1], ll.read_input_of_group(page)),
        (["Todo", 2, 2, True], ["Todo", "", True, True]),
    )
    page.keyboard.press("Escape")
    check.expect("Escape closes the input", lambda: ll.read_input_of_group(page), None)

    ll.open_input_of_group(page, "Done")
    page.keyboard.type("added to done")
    page.keyboard.press("Enter")
    check.expect(
        "in a group without work items: stored in its state, and the group shows its one line",
        lambda: (read_state(check, project, "added to done"), ll.read_groups(page)[3]),
        ("Done", ["Done", 1, 1, True]),
    )
    ll.select_line(page, "in backlog")
    check.expect(
        "a click elsewhere closes the input", lambda: ll.read_input_of_group(page), None
    )

    ll.group_header(page, "In Progress").get_by_text("In Progress").click()
    check.expect(
        "a click on the name of a group folds it",
        lambda: ll.read_groups(page)[2],
        ["In Progress", 1, 0, True],
    )
    ll.plus_of_group(page, "In Progress").click()
    check.expect(
        'the "+" of a folded group unfolds it and opens the input',
        lambda: (ll.read_groups(page)[2], ll.read_input_of_group(page)),
        (["In Progress", 1, 1, True], ["In Progress", "", True, True]),
    )
    page.keyboard.press("Escape")
    ll.plus_of_group(page, "Backlog").focus()
    page.keyboard.press("Enter")
    check.expect(
        'Enter on the "+" that has the focus opens the input, and does not fold the group',
        lambda: (ll.read_groups(page)[0], ll.read_input_of_group(page)),
        (["Backlog", 1, 1, True], ["Backlog", "", True, True]),
    )
    page.context.close()

    page = ll.open_list(check, account, project, group_by=None)
    check.expect(
        'a list that is not grouped has one header, with the "+"',
        lambda: [group[1:] for group in ll.read_groups(page)],
        [[5, 5, True]],
    )
    ll.open_input_of_group(page, "All work items")
    page.keyboard.type("added to all")
    page.keyboard.press("Enter")
    check.expect(
        "there Enter stores the work item in the state a project gives a new one",
        lambda: read_state(check, project, "added to all"),
        "Backlog",
    )
    page.context.close()
