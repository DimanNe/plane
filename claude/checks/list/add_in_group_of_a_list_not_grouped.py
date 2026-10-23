"""
A list that is not grouped has one "+", in the header of all its work items, and it opens the dialog of N I in the
state a project gives a new work item.
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
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.plus_of_group(page, "All work items").click()
    check.expect(
        'a list that is not grouped: its one "+" opens the dialog in the state a project gives a new work item',
        lambda: ag.read_dialog(page),
        ["State, Backlog", "Priority, None", True],
    )
    ag.close_dialog(page)
    page.context.close()
