"""
The header of every group of the list has a "+" right after its count. It opens the dialog of N I, with the caret in
its title, for a work item of what the group stands for: the group of the "+", whichever line is selected, and N I
afterwards takes the group of the selected line again. Ctrl+Enter stores the work item there with the description
given in the dialog, and its line is the selected one. The checks named after this one find the "+" in a list
grouped by priority, in a list that is not grouped, and in the list of a cycle and of a module.
"""

import playwright.sync_api as pw

import instance as ins
import list_add_in_group as ag
import list_layout as ll
import steps


def check_groups_of_state(
    check: steps.Check, project: ins.Project, page: pw.Page
) -> None:
    dialog: pw.Locator = page.locator(ll.CREATE_DIALOG)
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

    ll.select_line(page, "in backlog")
    ll.plus_of_group(page, "Todo").click()
    check.expect(
        'the "+" of Todo opens the dialog of N I in Todo, although a line of Backlog is selected, with the caret in '
        "its title",
        lambda: ag.read_dialog(page),
        ["State, Todo", "Priority, None", True],
    )
    page.keyboard.type("added to todo")
    dialog.locator(".ProseMirror").first.click()
    page.keyboard.type("with a description")
    page.keyboard.press("Control+Enter")
    check.expect(
        "Ctrl+Enter stores the work item in Todo, with its description",
        lambda: ag.read_stored(check, project, "added to todo"),
        ["Todo", "none", "with a description"],
    )
    check.expect(
        "the dialog is closed, the group shows and counts the work item, and its line is the selected one and is "
        "tinted",
        lambda: (
            dialog.count(),
            ll.read_groups(page)[1],
            ll.read_selected(page),
            ll.read_tinted(page),
        ),
        (0, ["Todo", 2, 2, True], ["added to todo"], ["added to todo"]),
    )

    ll.select_line(page, "in backlog")
    ll.open_create_dialog(page)
    check.expect(
        'N I after the "+" takes the group of the selected line again',
        lambda: ag.read_dialog(page),
        ["State, Backlog", "Priority, None", True],
    )
    ag.close_dialog(page)

    ll.plus_of_group(page, "Done").click()
    page.wait_for_function("() => document.activeElement?.name === 'name'")
    page.keyboard.type("added to done")
    page.keyboard.press("Control+Enter")
    check.expect(
        "in a group without work items: stored in its state, and the group shows its one line",
        lambda: (
            ag.read_stored(check, project, "added to done"),
            ll.read_groups(page)[3],
        ),
        (["Done", "none", ""], ["Done", 1, 1, True]),
    )

    ll.group_header(page, "In Progress").get_by_text("In Progress").click()
    check.expect(
        "a click on the name of a group folds it",
        lambda: ll.read_groups(page)[2],
        ["In Progress", 1, 0, True],
    )
    dialog.wait_for(state="detached")
    ll.plus_of_group(page, "In Progress").click()
    check.expect(
        'the "+" of a folded group unfolds it and opens the dialog in its state',
        lambda: (ll.read_groups(page)[2], ag.read_dialog(page)),
        (["In Progress", 1, 1, True], ["State, In Progress", "Priority, None", True]),
    )
    ag.close_dialog(page)
    ll.plus_of_group(page, "Backlog").focus()
    page.keyboard.press("Enter")
    check.expect(
        'Enter on the "+" that has the focus opens the dialog, and does not fold the group',
        lambda: (ll.read_groups(page)[0], ag.read_dialog(page)),
        (["Backlog", 1, 1, True], ["State, Backlog", "Priority, None", True]),
    )
    ag.close_dialog(page)


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project(
        {account: ins.ROLE_ADMIN}, cycle_view=True, module_view=True
    )
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
    check_groups_of_state(check, project, page)
    page.context.close()
