"""
Enter in the title of a work item puts the caret at the very beginning of its description, so that a title and its
description are typed as one text. In the dialog of a new work item, what is typed at once after Enter arrives in the
description, and Enter saves nothing; Ctrl+Enter still saves. In the view beside the list the title stays one line.
"""

import re

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

CARET_IN_DIALOG_DESCRIPTION_JS: str = """
() => !!document.activeElement?.classList.contains('ProseMirror') && !!document.activeElement.closest('[role="dialog"]')
"""
CARET_IN_VIEW_DESCRIPTION_JS: str = """
() => !!document.activeElement?.classList.contains('ProseMirror')
  && !!document.activeElement.closest('#full-screen-portal')
"""


def read_description(check: steps.Check, project: ins.Project, name: str) -> str:
    html: str = (
        ins.read_work_items(check.instance, project)[name].get("description_html") or ""
    )
    return re.sub(r"<[^>]+>", "", html).replace("&nbsp;", " ")


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [{"name": "with text", "description_html": "<p>existing text</p>"}],
    )
    page: pw.Page = ll.open_list(check, account, project)

    dialog: pw.Locator = ll.open_create_dialog(page)
    page.keyboard.type("a title")
    page.keyboard.press("Enter")
    page.keyboard.type("first words")
    check.expect(
        "in the dialog Enter takes the caret from the title to the description, and what is typed at once goes "
        "there; Enter saves nothing (title, description, caret in the description, work items on the server)",
        lambda: (
            dialog.locator('input[name="name"]').input_value(),
            dialog.locator(".ProseMirror").first.inner_text(),
            page.evaluate(CARET_IN_DIALOG_DESCRIPTION_JS),
            sorted(ins.read_work_items(check.instance, project)),
        ),
        ("a title", "first words", True, ["with text"]),
    )
    page.keyboard.press("Control+Enter")
    dialog.wait_for(state="detached")
    check.expect(
        "Ctrl+Enter saves the work item with its title and its description",
        lambda: read_description(check, project, "a title"),
        "first words",
    )

    ll.select_line(page, "with text")
    page.keyboard.press("Enter")
    title: pw.Locator = page.locator(ll.PANEL_TITLE)
    title.click()
    page.keyboard.press("End")
    page.keyboard.press("Enter")
    page.keyboard.type("word ")
    check.expect(
        "in the view beside the list Enter in the title puts the caret at the very beginning of the description, and "
        "the title stays one line (title, caret in the description)",
        lambda: (title.input_value(), page.evaluate(CARET_IN_VIEW_DESCRIPTION_JS)),
        ("with text", True),
    )
    check.expect(
        "the server has the description with the typed words before its text, and the title unchanged",
        lambda: (
            read_description(check, project, "with text"),
            sorted(ins.read_work_items(check.instance, project)),
        ),
        ("word existing text", ["a title", "with text"]),
    )
