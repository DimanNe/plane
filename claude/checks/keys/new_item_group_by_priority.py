"""
N I with a line of a list grouped by priority selected makes a new work item in that line's group: the dialog shows
the group's priority, and the work item is stored with it.
"""

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "high", "priority": "high"}])
    page: pw.Page = ll.open_list(check, account, project, group_by="priority")
    ll.select_line(page, "high")
    shown, stored = ll.make_with_keys(
        check, project, page, "new in a group of priorities"
    )
    check.expect(
        "grouped by priority: from a line of High, the dialog shows High, and the work item is stored so",
        lambda: (shown[1], stored["priority"]),
        ("High", "high"),
    )
    page.context.close()
