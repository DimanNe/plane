"""
In an open menu that has an item Edit, E does what a click on that item does: in the menu of a line of the list it
opens the dialog that edits the work item, and in the menu of a comment it makes the comment editable.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
import steps

# The dialog that edits a work item: the title in its field, and whether the caret is there.
EDIT_DIALOG_JS: str = """
() => {
  const dialog = [...document.querySelectorAll('[role="dialog"]')].find((d) => d.querySelector('input[name="name"]'));
  if (!dialog) return null;
  const title = dialog.querySelector('input[name="name"]');
  return [title.value, document.activeElement === title];
}
"""


def open_line_menu(page: pw.Page, title: str) -> None:
    ll.line(page, title).click(button="right", position={"x": 6, "y": 10})
    page_changes.wait_until_shown(page.get_by_role("menu"))
    page_changes.wait_until_true(
        page, "() => document.activeElement?.closest('[role=\"menu\"]')"
    )


def open_comment_menu(page: pw.Page, comment_id: str) -> None:
    """The menu of a comment, by the button of options of the card that holds it."""
    card: pw.Locator = page.locator(f'[id="editor-container-{comment_id}"]').first
    card.scroll_into_view_if_needed()
    card.hover()
    page.locator(
        f'xpath=//*[@id="editor-container-{comment_id}"]/ancestor::*[.//button[@aria-label="Options"]][1]'
    ).get_by_role("button", name="Options").last.click()
    page_changes.wait_until_shown(page.get_by_role("menu"))
    page_changes.wait_until_true(
        page, "() => document.activeElement?.closest('[role=\"menu\"]')"
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance, project, [{"name": "edited"}]
    )
    # by the account itself: only who wrote a comment may edit it
    comment: ins.JSONObject = ins.call_app(
        check.instance.url,
        account,
        "POST",
        f"/workspaces/{check.instance.workspace}/projects/{project.id}/issues/{ids['edited']}/comments/",
        {"comment_html": "<p>a comment</p>"},
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    open_line_menu(page, "edited")
    page.get_by_role("menuitem", name="Edit").click()
    check.expect(
        "a click on Edit in the menu of a line opens the dialog that edits the work item, the caret in its title",
        lambda: page.evaluate(EDIT_DIALOG_JS),
        ["edited", True],
    )
    page.keyboard.press("Escape")
    page_changes.wait_until_removed(page.locator(ll.CREATE_DIALOG))
    open_line_menu(page, "edited")
    page.keyboard.press("e")
    check.expect(
        "E in that menu opens the same, and closes the menu",
        lambda: (page.evaluate(EDIT_DIALOG_JS), page.get_by_role("menu").count()),
        (["edited", True], 0),
    )
    page.keyboard.press("Escape")
    page_changes.wait_until_removed(page.locator(ll.CREATE_DIALOG))

    ll.select_line(page, "edited")
    page.keyboard.press("Enter")
    page_changes.wait_until_shown(page.locator(ll.PANEL_TITLE))
    open_comment_menu(page, comment["id"])
    page.keyboard.press("e")
    check.expect(
        "E in the menu of a comment makes the comment editable, as Edit does, and closes the menu",
        lambda: (
            page.locator(
                f'[id="editor-container-{comment["id"]}"] .ProseMirror[contenteditable="true"]'
            ).count(),
            page.get_by_role("menu").count(),
        ),
        (1, 0),
    )
    page.context.close()
