"""
The arrow keys are the list's after a dialog that a key opened has closed: the focus goes back to the page, not to a
control the person used before, such as the workspace switcher, whose menu Arrow Down would open. With no line
selected an arrow key starts at the last click in the list: after a click on the header of an empty group, Arrow
Down selects the first line below it, in the next group that has one, and Arrow Up the last line above it.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

MENU: str = '[role="menu"]'


def read_focus_menus_and_selected(page: pw.Page) -> t.Tuple[str, int, t.List[str]]:
    return ll.read_focus(page), page.locator(MENU).count(), ll.read_selected(page)


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "first in backlog", "state": "Backlog"},
            {"name": "waiting in backlog", "state": "Backlog"},
            {"name": "being done", "state": "In Progress"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)

    # Before: the workspace switcher was used, and its menu closed again, which gives the focus back to it.
    switcher: pw.Locator = page.get_by_role(
        "button", name="Open workspace switcher"
    ).first
    switcher.click()
    page.locator(MENU).first.wait_for()
    page.keyboard.press("Escape")
    page.locator(MENU).first.wait_for(state="detached")

    ll.group_header(page, "Todo").get_by_text("Todo", exact=True).first.click()
    ll.open_create_dialog(page)
    page.keyboard.press("Escape")
    page.locator(ll.CREATE_DIALOG).wait_for(state="detached")
    check.expect(
        "a click on the empty Todo, N I and Escape: the focus is on the page again (the focus, menus open, selected)",
        lambda: read_focus_menus_and_selected(page),
        ("page", 0, []),
    )
    page.keyboard.press("ArrowDown")
    check.expect(
        "and Arrow Down opens no menu: it selects the first line below the click, in In Progress (the focus, "
        "menus open, selected)",
        lambda: read_focus_menus_and_selected(page)[1:],
        (0, ["being done"]),
    )

    page.keyboard.press("Escape")
    page.reload()
    ll.line(page, "being done").wait_for()
    ll.group_header(page, "Todo").get_by_text("Todo", exact=True).first.click()
    page.keyboard.press("ArrowUp")
    check.expect(
        "with no line selected, a click on the empty Todo and Arrow Up select the last line above it, the second "
        "in Backlog",
        lambda: ll.read_selected(page),
        ["waiting in backlog"],
    )
    page.context.close()
