"""
In a list grouped by priority, the "+" in the header of a group opens the dialog of N I with the priority of the
group, and Ctrl+Enter stores the work item with it.
"""

import playwright.sync_api as pw

import instance as ins
import list_add_in_group as ag
import list_layout as ll
import steps


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
    page: pw.Page = ll.open_list(check, account, project, group_by="priority")
    ll.plus_of_group(page, "High").click()
    check.expect(
        'grouped by priority: the "+" of High opens the dialog with that priority',
        lambda: ag.read_dialog(page),
        ["State, Backlog", "Priority, High", True],
    )
    page.keyboard.type("added to high")
    page.keyboard.press("Control+Enter")
    check.expect(
        "and stores the work item with it",
        lambda: ag.read_stored(check, project, "added to high"),
        ["Backlog", "high", ""],
    )
    page.context.close()
