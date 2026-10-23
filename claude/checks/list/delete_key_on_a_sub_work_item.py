"""
Delete on the selected line of a sub-work item deletes that one alone, and the selection goes to the line that took
its place.
"""

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "parent"},
            {"name": "child one", "parent": "parent"},
            {"name": "child two", "parent": "parent"},
            {"name": "after"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    ll.select_line(page, "child one")
    page.keyboard.press("Shift+Delete")
    check.expect(
        "a sub-work item is deleted alone, and the selection is on the line that took its place",
        lambda: (
            ll.read_lines(page),
            ll.read_selected(page),
            ins.read_work_item_names(check.instance, project),
        ),
        (
            [
                ["Backlog", 0, "parent"],
                ["Backlog", 1, "child two"],
                ["Backlog", 0, "after"],
            ],
            ["child two"],
            ["after", "child two", "parent"],
        ),
    )
    page.context.close()
