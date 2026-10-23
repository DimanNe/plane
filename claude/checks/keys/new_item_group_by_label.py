"""
N I with a line of a list grouped by label selected makes a new work item in that line's group: the dialog shows the
group's label, and the work item is stored with it.
"""

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    label: ins.JSONObject = ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/labels/",
        {"name": "red", "color": "#cc3355"},
    )
    ins.make_work_items(
        check.instance, project, [{"name": "labelled", "labels": [label["id"]]}]
    )
    page: pw.Page = ll.open_list(check, account, project, group_by="labels")
    ll.select_line(page, "labelled")
    shown, stored = ll.make_with_keys(check, project, page, "new in a group of labels")
    check.expect(
        "grouped by label: from a line of red, the dialog shows red, and the work item is stored with it",
        lambda: (shown[2], stored["labels"]),
        ("red", [label["id"]]),
    )
    page.context.close()
