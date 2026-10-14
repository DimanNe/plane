"""
The lists of a cycle, a module, the user's own work and the archive are drawn by the same list as a project's
work items, so what the fork gave that list holds there too: the state circle, a selection that a click makes
and the arrow keys move, the entries for a filter on a right click (but in the user's own work, whose filters
are its own); and in the archive, where nothing can be changed, a line without a "..." button.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps


def check_shared_list(
    check: steps.Check, page: pw.Page, where: str, has_filter: bool
) -> None:
    page.get_by_role("button", name="List Layout").first.click()
    page.locator(ll.LINE).first.wait_for()
    check.expect(
        f"{where}: the lines have the state circle",
        lambda: page.locator(f'{ll.LINE} button[aria-label^="State, "]').count()
        == page.locator(ll.LINE).count(),
        True,
    )
    titles: t.List[str] = ll.read_titles(page)
    ll.select_line(page, titles[0])
    page.keyboard.press("ArrowDown")
    check.expect(
        f"{where}: a click selects a line and Arrow Down moves the selection",
        lambda: ll.read_selected(page),
        titles[1:2],
    )
    ll.line(page, "two").locator('button[aria-label^="State, "]').click(button="right")
    page.get_by_role("menu").wait_for()
    check.expect(
        f"{where}: a right click on the state offers the filter by it"
        if has_filter
        else f"{where}: a right click on the state opens the line's menu, which has no entries for a filter",
        lambda: page.get_by_role("menuitem", name="Show only State: Todo").count(),
        1 if has_filter else 0,
    )
    page.keyboard.press("Escape")


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project(
        {account: ins.ROLE_ADMIN}, cycle_view=True, module_view=True
    )
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": name, "state": "Todo", "assignees": [account.user_id]}
            for name in ("one", "two")
        ]
        + [{"name": "done", "state": "Done"}],
    )
    workspace: str = f"/{check.instance.workspace}"
    projects: str = f"{workspace}/projects/{project.id}"
    cycle: str = ins.call_api(
        check.instance, "POST", f"/projects/{project.id}/cycles/", {"name": "a cycle"}
    )["id"]
    ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/cycles/{cycle}/cycle-issues/",
        {"issues": [ids["one"], ids["two"]]},
    )
    module: str = ins.call_api(
        check.instance, "POST", f"/projects/{project.id}/modules/", {"name": "a module"}
    )["id"]
    ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/modules/{module}/module-issues/",
        {"issues": [ids["one"], ids["two"]]},
    )

    page: pw.Page = browser.open_page(check, account, f"{projects}/cycles/{cycle}/")
    check_shared_list(check, page, "the list of a cycle", has_filter=True)
    page.goto(f"{check.instance.url}{projects}/modules/{module}/")
    check_shared_list(check, page, "the list of a module", has_filter=True)
    page.goto(f"{check.instance.url}{workspace}/profile/{account.user_id}/assigned/")
    check_shared_list(check, page, "the user's own work", has_filter=False)

    ins.call_app(
        check.instance.url,
        account,
        "POST",
        f"/workspaces/{check.instance.workspace}/projects/{project.id}/issues/{ids['done']}/archive/",
    )
    page.goto(f"{check.instance.url}{projects}/archives/issues/")
    line: pw.Locator = ll.line(page, "done")
    line.wait_for()
    line.hover()
    check.expect(
        'the archive: a line shows no "..." button, also under the pointer',
        lambda: line.locator('button[aria-haspopup="menu"]')
        .locator("visible=true")
        .count(),
        0,
    )
    line.locator("p").first.click(button="right")
    check.expect(
        "a right click opens its one menu", lambda: page.get_by_role("menu").count(), 1
    )
    page.context.close()
