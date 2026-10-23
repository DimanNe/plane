"""
↑ on the first line of a work item's description puts the caret at the end of its title, so that the title and its
description are gone through as one text, as Enter in the title goes on in the description. On any later line, a later
line of a first paragraph that wraps too, ↑ stays in the description. What is typed after ↑ goes to the title. So it is
in the dialog of a new work item, in the view beside the list, in the work item's own page and in intake.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

# Where the caret is: at the end of the title, elsewhere in the title, in the description (the editable part that
# follows the title, as the app finds it), in another editor such as that of a comment, or the element it is in.
CARET_JS: str = """
() => {
  const element = document.activeElement;
  if (element?.name === 'name' || element?.id === 'title-input')
    return element.selectionStart === element.value.length && element.selectionEnd === element.value.length
      ? 'at the end of the title' : 'in the title';
  const title = document.querySelector('[role="dialog"] input[name="name"]') ?? document.querySelector('#title-input');
  const description = title && [...document.querySelectorAll('[contenteditable="true"]')].find(
    (editable) => title.compareDocumentPosition(editable) & Node.DOCUMENT_POSITION_FOLLOWING);
  if (element && element === description) return 'in the description';
  if (element?.classList.contains('ProseMirror')) return 'in another editor';
  return element?.tagName ?? null;
}
"""
# The number of lines the first paragraph of the description in `root` is drawn on.
FIRST_PARAGRAPH_LINES_JS: str = """
(root) => {
  const paragraph = root.querySelector('.ProseMirror p');
  return Math.round(paragraph.getBoundingClientRect().height / parseFloat(getComputedStyle(paragraph).lineHeight));
}
"""
# A description of two lines; the editor that holds it is the description, not the empty one of a new comment, which
# a page under load may have drawn first.
DESCRIPTION: str = "<p>first line</p><p>second line</p>"


def check_arrow_up_from_second_line(
    check: steps.Check,
    page: pw.Page,
    where: str,
    title: pw.Locator,
    description: pw.Locator,
) -> None:
    """From the end of the description's second line, ↑ twice and a key, in a place whose description is DESCRIPTION."""
    # to the end of the description, its second line: a click alone leaves the caret where the page last put it
    description.click()
    page.keyboard.press("Control+End")
    name: str = title.input_value()
    page.keyboard.press("ArrowUp")
    check.expect(
        f"{where}: ↑ on the second line of the description stays in the description",
        lambda: page.evaluate(CARET_JS),
        "in the description",
    )
    page.keyboard.press("ArrowUp")
    check.expect(
        f"{where}: ↑ on the first line of the description puts the caret at the end of the title",
        lambda: page.evaluate(CARET_JS),
        "at the end of the title",
    )
    page.keyboard.type("!")
    check.expect(
        f"{where}: what is typed after it goes to the title (title, description)",
        lambda: (title.input_value(), description.locator("p").all_inner_texts()),
        (f"{name}!", ["first line", "second line"]),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    # the API makes a project's intake when an update turns it on, not when the project is made with it on
    ins.call_api(
        check.instance, "PATCH", f"/projects/{project.id}/", {"intake_view": True}
    )
    ins.make_work_items(
        check.instance,
        project,
        [{"name": "with text", "description_html": DESCRIPTION}],
    )
    intake_item: ins.JSONObject = ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/intake-issues/",
        {"issue": {"name": "for intake", "description_html": DESCRIPTION}},
    )
    page: pw.Page = ll.open_list(check, account, project)

    dialog: pw.Locator = ll.open_create_dialog(page)
    page.keyboard.type("a title")
    page.keyboard.press("Enter")
    page.keyboard.type("words " * 30)
    page.keyboard.press("Enter")
    page.keyboard.type("second line")
    lines: int = dialog.evaluate(FIRST_PARAGRAPH_LINES_JS)
    check.expect_at_least(
        "in the dialog the first paragraph of the description wraps (its lines)",
        lines,
        2,
    )
    # from the second paragraph up to the first line of the first, through each line it wraps into
    for _ in range(lines):
        page.keyboard.press("ArrowUp")
    check.expect(
        "in the dialog ↑ on the lower lines of a first paragraph that wraps stays in the description",
        lambda: page.evaluate(CARET_JS),
        "in the description",
    )
    page.keyboard.press("ArrowUp")
    check.expect(
        "in the dialog ↑ on the first line of the description puts the caret at the end of the title",
        lambda: page.evaluate(CARET_JS),
        "at the end of the title",
    )
    page.keyboard.type("!")
    check.expect(
        "in the dialog what is typed after it goes to the title (title, the description's last paragraph)",
        lambda: (
            dialog.locator('input[name="name"]').input_value(),
            dialog.locator(".ProseMirror p").last.inner_text(),
        ),
        ("a title!", "second line"),
    )
    page.keyboard.press("Control+Enter")
    dialog.wait_for(state="detached")

    ll.select_line(page, "with text")
    page.keyboard.press("Enter")
    check_arrow_up_from_second_line(
        check,
        page,
        "in the view beside the list",
        page.locator(ll.PANEL_TITLE),
        page.locator("#full-screen-portal .ProseMirror", has_text="second line"),
    )

    work_item_page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/browse/{project.identifier}-1/"
    )
    check_arrow_up_from_second_line(
        check,
        work_item_page,
        "in the work item's page",
        work_item_page.locator("#title-input"),
        work_item_page.locator(".ProseMirror", has_text="second line"),
    )

    description: pw.Locator = work_item_page.locator(
        ".ProseMirror", has_text="second line"
    )
    description.click()
    work_item_page.keyboard.press("Control+Home")
    work_item_page.keyboard.type("/")
    work_item_page.locator("#slash-command").wait_for()
    work_item_page.keyboard.press("ArrowUp")
    check.expect(
        "in the work item's page ↑ on the first line moves in the open menu of / and leaves the caret in the "
        "description (caret, the menu shown)",
        lambda: (
            work_item_page.evaluate(CARET_JS),
            work_item_page.locator("#slash-command").is_visible(),
        ),
        ("in the description", True),
    )
    work_item_page.keyboard.press("Escape")
    work_item_page.keyboard.press("Backspace")

    intake: pw.Page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/projects/{project.id}/intake/?currentTab=open&inboxIssueId={intake_item['issue']}",
    )
    check_arrow_up_from_second_line(
        check,
        intake,
        "in intake",
        intake.locator("#title-input"),
        intake.locator(".ProseMirror", has_text="second line"),
    )
