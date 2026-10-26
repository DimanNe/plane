"""
↓ on the last line of a work item's title puts the caret at the start of its description, as Enter does, so that ↓
goes on from the title into the description as ↑ goes back (keys/arrow_up_in_description). On an earlier line of a
title that wraps ↓ stays in the title, at the end of such a line too, and so does ↓ with Shift or over a selection.
What is typed after ↓ goes to the description, an empty one too, and a ↓ pressed at once goes on down the description.
So it is in the dialog of a new work item, in the view beside the list, in the work item's own page and in intake.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import page_changes
import steps

# Where the caret is: in the title, at the start of the description (the editable part that follows the title, as
# the app finds it), on another line of it, in another editor such as that of a comment, or the element it is in.
CARET_JS: str = """
() => {
  const element = document.activeElement;
  if (element?.name === 'name' || element?.id === 'title-input') return 'in the title';
  const title = document.querySelector('[role="dialog"] input[name="name"]') ?? document.querySelector('#title-input');
  const description = title && [...document.querySelectorAll('[contenteditable="true"]')].find(
    (editable) => title.compareDocumentPosition(editable) & Node.DOCUMENT_POSITION_FOLLOWING);
  if (element?.classList.contains('ProseMirror') && element !== description) return 'in another editor';
  if (!element || element !== description) return element?.tagName ?? null;
  const selection = getSelection();
  const node = selection.focusNode;
  const line = (node instanceof Element ? node : node?.parentElement)?.closest('p');
  if (!line) return 'in the description, on no line';
  const beforeCaret = document.createRange();
  beforeCaret.setStart(line, 0);
  beforeCaret.setEnd(node, selection.focusOffset);
  if (line === description.querySelector('p') && selection.isCollapsed && beforeCaret.toString() === '')
    return 'at the start of the description';
  return `on the line "${line.textContent}"`;
}
"""
# The number of lines the textarea of a title is drawn on.
TITLE_LINES_JS: str = """
(title) => {
  const style = getComputedStyle(title);
  const text = title.scrollHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
  return Math.round(text / parseFloat(style.lineHeight));
}
"""
DESCRIPTION: str = "<p>first line</p><p>second line</p>"
# A title that the view beside the list wraps over several lines.
LONG_TITLE: str = ("words " * 30).strip()


def read_caret(page: pw.Page) -> t.Optional[str]:
    return page.evaluate(CARET_JS)


def read_title_and_description(
    title: pw.Locator, description: pw.Locator
) -> t.Tuple[str, t.List[str]]:
    return title.input_value(), description.locator("p").all_inner_texts()


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    # the API makes a project's intake when an update turns it on, not when the project is made with it on
    ins.call_api(
        check.instance, "PATCH", f"/projects/{project.id}/", {"intake_view": True}
    )
    # one work item for each place, so that what is typed in one is not saved while another shows it
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": LONG_TITLE, "description_html": DESCRIPTION},
            {"name": "for its page", "description_html": DESCRIPTION},
        ],
    )
    intake_item: ins.JSONObject = ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/intake-issues/",
        {"issue": {"name": "for intake", "description_html": DESCRIPTION}},
    )
    page: pw.Page = ll.open_list(check, account, project)

    dialog: pw.Locator = ll.open_create_dialog(page)
    page_changes.wait_until_shown(dialog.locator(".ProseMirror"))
    page.keyboard.type("a title")
    page.keyboard.press("ArrowDown")
    check.expect(
        "in the dialog ↓ in the title puts the caret at the start of the empty description",
        lambda: read_caret(page),
        "at the start of the description",
    )
    page.keyboard.type("words")
    check.expect(
        "in the dialog what is typed after it goes to the description (title, description)",
        lambda: (
            dialog.locator('input[name="name"]').input_value(),
            dialog.locator(".ProseMirror p").all_inner_texts(),
        ),
        ("a title", ["words"]),
    )
    page.keyboard.press("Control+Enter")
    page_changes.wait_until_removed(dialog)

    ll.select_line(page, LONG_TITLE)
    page.keyboard.press("Enter")
    title: pw.Locator = page.locator(ll.PANEL_TITLE)
    description: pw.Locator = page.locator(
        "#full-screen-portal .ProseMirror", has_text="second line"
    )
    page_changes.wait_until_shown(description)
    title.click()
    page.keyboard.press("Control+Home")
    lines: int = title.evaluate(TITLE_LINES_JS)
    check.expect_at_least(
        "in the view beside the list the title wraps (its lines)", lines, 2
    )
    line: int
    for line in range(1, lines - 1):
        page.keyboard.press("ArrowDown")
        check.expect(
            f"in the view beside the list ↓ on line {line} of the title's {lines} stays in the title",
            lambda: read_caret(page),
            "in the title",
        )
    # End puts the caret at the offset where this line wraps, which is also the start of the last line
    page.keyboard.press("End")
    page.keyboard.press("ArrowDown")
    check.expect(
        f"in the view beside the list ↓ at the end of line {lines - 1} of the title's {lines} stays in the title",
        lambda: read_caret(page),
        "in the title",
    )
    page.keyboard.press("ArrowDown")
    check.expect(
        "in the view beside the list ↓ on the last line of the title puts the caret at the start of the description",
        lambda: read_caret(page),
        "at the start of the description",
    )
    page.keyboard.type("!")
    check.expect(
        "in the view beside the list what is typed after it goes to the description (title, description)",
        lambda: read_title_and_description(title, description),
        (LONG_TITLE, ["!first line", "second line"]),
    )

    work_item_page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/browse/{project.identifier}-2/"
    )
    title = work_item_page.locator("#title-input")
    description = work_item_page.locator(".ProseMirror", has_text="second line")
    page_changes.wait_until_shown(description)
    title.click()
    work_item_page.keyboard.press("End")
    # the second ↓ moves the caret right after the description took the focus, as a held ↓ repeats
    work_item_page.keyboard.press("ArrowDown")
    work_item_page.keyboard.press("ArrowDown")
    check.expect(
        "in the work item's page ↓ at once after ↓ from the title goes on down the description",
        lambda: read_caret(work_item_page),
        'on the line "second line"',
    )
    work_item_page.keyboard.type("!")
    check.expect(
        "in the work item's page what is typed then goes to the description's second line (title, description)",
        lambda: read_title_and_description(title, description),
        ("for its page", ["first line", "!second line"]),
    )

    intake: pw.Page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/projects/{project.id}/intake/?currentTab=open&inboxIssueId={intake_item['issue']}",
    )
    title = intake.locator("#title-input")
    description = intake.locator(".ProseMirror", has_text="second line")
    page_changes.wait_until_shown(description)
    title.click()
    intake.keyboard.press("End")
    intake.keyboard.press("Shift+ArrowDown")
    check.expect(
        "in intake Shift+↓ on the last line of the title stays in the title",
        lambda: read_caret(intake),
        "in the title",
    )
    intake.keyboard.press("Shift+Home")
    intake.keyboard.press("ArrowDown")
    check.expect(
        "in intake ↓ over a selection in the title stays in the title",
        lambda: read_caret(intake),
        "in the title",
    )
    intake.keyboard.press("End")
    intake.keyboard.press("ArrowDown")
    check.expect(
        "in intake ↓ on the last line of the title puts the caret at the start of the description",
        lambda: read_caret(intake),
        "at the start of the description",
    )
    intake.keyboard.type("!")
    check.expect(
        "in intake what is typed after it goes to the description (title, description)",
        lambda: read_title_and_description(title, description),
        ("for intake", ["!first line", "second line"]),
    )
