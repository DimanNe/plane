"""
A work item that cannot be loaded after E: the view says so, and Escape closes it, the keys being the list's again.
"""

import re
import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "slow"},
            {"name": "unloadable"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    page.route(
        re.compile(rf"/issues/{ids['unloadable']}/(\?.*)?$"),
        lambda route: route.fulfill(status=404, json={"error": "not found"}),
    )
    ll.select_line(page, "unloadable")
    page.keyboard.press("e")
    check.expect(
        "a work item that cannot be loaded: the view says so",
        lambda: page.locator("#full-screen-portal").inner_text().split("\n")[0],
        "Work item does not exist",
    )
    page.keyboard.press("Escape")
    page.keyboard.press("ArrowUp")
    check.expect(
        "and Escape closes it, the keys being the list's again",
        lambda: ll.read_selected(page),
        ["slow"],
    )
    page.context.close()
