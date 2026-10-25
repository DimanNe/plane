"""
A work item that loads slowly after E gets everything typed meanwhile: while it loads nothing has the caret, no
dialog opens and the selection stays; when it has come, what was typed meanwhile is in its description, before what
is typed after.
"""

import re
import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "slow"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)

    # the answers with the work item are kept back until the step lets them through
    kept_back: t.List[pw.Route] = []
    work_item: t.Pattern[str] = re.compile(rf"/issues/{ids['slow']}/(\?.*)?$")
    page.route(
        work_item,
        lambda route: kept_back.append(route)
        if route.request.method == "GET"
        else route.continue_(),
    )
    ll.select_line(page, "slow")
    page.keyboard.press("e")
    page.keyboard.type("nc sd while it loads ", delay=40)
    check.expect(
        "while the work item loads, nothing has the caret, no dialog opens and the selection stays",
        lambda: (
            len(kept_back) > 0,
            page.evaluate("() => document.activeElement.isContentEditable"),
            page.locator(ll.CREATE_DIALOG).count(),
            ll.read_selected(page),
        ),
        (True, False, 0, ["slow"]),
    )
    route: pw.Route
    for route in kept_back:
        route.continue_()
    # Playwright hands a request to the check only while the check calls it, and the reads below go to the server;
    # so nothing of the work item is held any more
    page.unroute(work_item)
    page_changes.wait_until_true(page, ll.CARET_IN_DESCRIPTION_JS, arg=ids["slow"])
    page.keyboard.type("and after")
    check.expect(
        "when it has come, what was typed meanwhile is in its description, before what is typed after",
        lambda: ll.read_description(check, project, "slow"),
        "nc sd while it loads and after",
    )
    page.keyboard.press("Escape")
    page_changes.wait_until_removed(page.locator(ll.PANEL_TITLE))
    page.context.close()
