"""
In a comment Enter begins a new line and sends nothing, and Ctrl+Enter sends the comment once and empties the editor;
Ctrl+Enter in an empty comment sends nothing. In a comment that is edited Enter is a new line too, and Ctrl+Enter
saves it once. The button Comment still sends.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import page_changes
import steps

EDITOR: str = '#full-screen-portal .ProseMirror[contenteditable="true"]'


def open_comment_menu(page: pw.Page, comment_id: str) -> None:
    """The menu of a comment, by the button of options of the card that holds it."""
    card: pw.Locator = page.locator(f'[id="editor-container-{comment_id}"]').first
    card.scroll_into_view_if_needed()
    card.hover()
    page.locator(
        f'xpath=//*[@id="editor-container-{comment_id}"]/ancestor::*[.//button[@aria-label="Options"]][1]'
    ).get_by_role("button", name="Options").last.click()
    page_changes.wait_until_shown(page.get_by_role("menu"))


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance, project, [{"name": "talked about"}]
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    writes: t.List[str] = browser.record_writes(page)
    ll.select_line(page, "talked about")
    page.keyboard.press("Enter")
    page_changes.wait_until_shown(page.locator(ll.PANEL_TITLE))
    comment: pw.Locator = page.locator(EDITOR).last
    comment.click()
    page.keyboard.type("first line")
    page.keyboard.press("Enter")
    page.keyboard.type("second line")
    check.expect_stays(
        "in a new comment Enter begins a new line and sends nothing",
        lambda: [
            write for write in browser.read_writes(page, writes) if "comment" in write
        ],
        [],
    )
    page.keyboard.press("Control+Enter")
    check.expect(
        "Ctrl+Enter sends the comment once, both lines, and empties the editor",
        lambda: (
            ll.read_comments(check, project, ids["talked about"]),
            len(
                [
                    write
                    for write in browser.read_writes(page, writes)
                    if write.startswith("POST") and "comment" in write
                ]
            ),
            page.locator(EDITOR).last.inner_text().strip(),
        ),
        ([["first line", "second line"]], 1, ""),
    )
    writes.clear()
    page.locator(EDITOR).last.click()
    page.keyboard.press("Control+Enter")
    check.expect_stays(
        "Ctrl+Enter in an empty comment sends nothing",
        lambda: [
            write for write in browser.read_writes(page, writes) if "comment" in write
        ],
        [],
    )
    page.keyboard.type("by the button")
    page.locator("#full-screen-portal").get_by_role(
        "button", name="Comment", exact=True
    ).click()
    check.expect(
        "the button Comment still sends",
        lambda: ll.read_comments(check, project, ids["talked about"])[-1],
        ["by the button"],
    )
    first: ins.JSONObject = sorted(
        ins.call_api(
            check.instance,
            "GET",
            f"/projects/{project.id}/work-items/{ids['talked about']}/comments/",
        )["results"],
        key=lambda comment: comment["created_at"],
    )[0]
    open_comment_menu(page, first["id"])
    page.get_by_role("menuitem", name="Edit").click()
    editable: pw.Locator = page.locator(
        f'[id="editor-container-{first["id"]}"] .ProseMirror[contenteditable="true"]'
    )
    editable.click()
    writes.clear()
    page.keyboard.press("Control+Home")
    page.keyboard.type("edited")
    page.keyboard.press("Enter")
    check.expect_stays(
        "in a comment that is edited Enter begins a new line and sends nothing",
        lambda: [
            write for write in browser.read_writes(page, writes) if "comment" in write
        ],
        [],
    )
    page.keyboard.press("Control+Enter")
    check.expect(
        "Ctrl+Enter saves it once",
        lambda: (
            ll.read_comments(check, project, ids["talked about"])[0],
            len(
                [
                    write
                    for write in browser.read_writes(page, writes)
                    if write.startswith("PATCH") and "comment" in write
                ]
            ),
        ),
        (["edited", "first line", "second line"], 1),
    )
    page.context.close()
