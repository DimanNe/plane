"""
N I with a line of a list grouped by state selected makes a new work item in that line's group: the dialog shows the
group's state, and the work item is stored with it. A dialog in which nothing was typed closes on Escape without a
question.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
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
    page: pw.Page = ll.open_list(check, account, project, group_by="state")
    ll.select_line(page, "started")
    shown, stored = ll.make_with_keys(check, project, page, "new in a group of states")
    check.expect(
        "grouped by state: N I from a line in In Progress shows In Progress, and the work item is stored there",
        lambda: (shown[0], states[stored["state"]]),
        ("In Progress", "In Progress"),
    )
    page.keyboard.press("n")
    page.keyboard.press("i")
    page_changes.wait_until_shown(page.locator(ll.CREATE_DIALOG))
    page.keyboard.press("Escape")
    check.expect(
        "a dialog in which nothing was typed closes on Escape, without a question",
        lambda: (
            page.locator(ll.CREATE_DIALOG).count(),
            page.locator(ll.QUESTION).count(),
        ),
        (0, 0),
    )
    page.context.close()
