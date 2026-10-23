"""
N I with a line of a list that is not grouped selected: the dialog shows the project's default state, as it always
did, and no priority, whatever the selected line has.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    states: t.Dict[str, str] = {
        state_id: name for name, state_id in project.states.items()
    }
    ins.make_work_items(
        check.instance, project, [{"name": "started", "state": "In Progress"}]
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(page, "started")
    shown, stored = ll.make_with_keys(check, project, page, "new in a list not grouped")
    check.expect(
        "in a list that is not grouped, the dialog shows the project's default state and no priority",
        lambda: (shown[:2], states[stored["state"]], stored["priority"]),
        (["Backlog", "None"], "Backlog", "none"),
    )
    page.context.close()
