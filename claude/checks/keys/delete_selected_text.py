"""
Delete and Backspace over selected text delete that text and nothing else, however it was selected: backwards from
the end of a line with Shift+Home or with the pointer, or forwards with Shift+End, in an item of a list and in a
paragraph, also when the key comes at once after the one that selected, before the browser has told the editor of
the new selection. Delete over an item of a list selected backwards does not join the next item to it. So it is in
the view beside the list, in the work item's own page and in the dialog of N I, and the server stores what is shown.
"""

import re
import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import page_changes
import steps

BY_SHIFT_HOME: str = "selected by Shift+Home"
BY_POINTER: str = "selected backwards by the pointer"
AT_ONCE: str = "selected by Shift+Home and deleted at once"
BY_SHIFT_END: str = "selected by Shift+End"
PARAGRAPH_AT_ONCE: str = "a paragraph selected by Shift+Home and deleted at once"
PARAGRAPH_BACKSPACE_AT_ONCE: str = (
    "a paragraph selected by Shift+End and Backspace at once"
)
# The lines of the description in the view beside the list: those that are selected and deleted, each between two
# that stay, so that a Delete that joins lines changes a line that stays.
LIST_LINES: t.List[str] = [
    "apple",
    BY_SHIFT_HOME,
    "pear",
    BY_POINTER,
    "plum",
    AT_ONCE,
    "cherry",
    BY_SHIFT_END,
    "lemon",
]
PARAGRAPH_LINES: t.List[str] = [
    "melon",
    PARAGRAPH_AT_ONCE,
    "peach",
    PARAGRAPH_BACKSPACE_AT_ONCE,
    "grape",
]

# Whether the editor that has the focus holds the selection that the page shows, as after a person's pause: the
# browser tells the editor of a selection that a key or the pointer has made a moment after it shows it. Tiptap
# keeps its editor on the editable element for tests.
EDITOR_HOLDS_SELECTION_JS: str = """
() => {
  const editor = document.activeElement?.closest('.ProseMirror')?.editor;
  const shown = getSelection();
  if (!editor || !shown.anchorNode || !editor.view.dom.contains(shown.anchorNode)) return false;
  const { anchor, head } = editor.state.selection;
  return anchor === editor.view.posAtDOM(shown.anchorNode, shown.anchorOffset)
    && head === editor.view.posAtDOM(shown.focusNode, shown.focusOffset);
}
"""
LINES_JS: str = (
    "(editable) => [...editable.querySelectorAll('p')].map((line) => line.textContent)"
)
# Where the text of a line begins and ends, and its middle in height.
TEXT_BOX_JS: str = """
(line) => {
  const text = document.createRange();
  text.selectNodeContents(line);
  const box = text.getBoundingClientRect();
  return [box.left, box.right, box.top + box.height / 2];
}
"""


def to_list(lines: t.List[str]) -> str:
    return "<ul>" + "".join(f"<li><p>{line}</p></li>" for line in lines) + "</ul>"


def to_paragraphs(lines: t.List[str]) -> str:
    return "".join(f"<p>{line}</p>" for line in lines)


def read_lines(editable: pw.Locator) -> t.List[str]:
    return editable.evaluate(LINES_JS)


def read_stored_lines(
    check: steps.Check, project: ins.Project, name: str
) -> t.List[str]:
    html: str = (
        ins.read_work_items(check.instance, project)[name].get("description_html") or ""
    )
    return [
        re.sub(r"<[^>]+>", "", line) for line in re.findall(r"<p[^>]*>(.*?)</p>", html)
    ]


def empty_line(lines: t.List[str], text: str) -> t.List[str]:
    return ["" if line == text else line for line in lines]


def find_line(editable: pw.Locator, text: str) -> pw.Locator:
    return editable.locator("p").filter(has_text=re.compile(f"^{re.escape(text)}$"))


def wait_until_editor_holds_selection(page: pw.Page) -> None:
    page_changes.wait_until_true(page, EDITOR_HOLDS_SELECTION_JS)


def put_caret_at_end(page: pw.Page, editable: pw.Locator, text: str) -> None:
    find_line(editable, text).click()
    page.keyboard.press("End")
    wait_until_editor_holds_selection(page)


def put_caret_at_start(page: pw.Page, editable: pw.Locator, text: str) -> None:
    find_line(editable, text).click()
    page.keyboard.press("Home")
    wait_until_editor_holds_selection(page)


def select_backwards_with_pointer(
    page: pw.Page, editable: pw.Locator, text: str
) -> None:
    """A press right of the end of the line's text, and a drag to the left past its start."""
    line: pw.Locator = find_line(editable, text)
    line.scroll_into_view_if_needed()
    left: float
    right: float
    middle: float
    left, right, middle = line.evaluate(TEXT_BOX_JS)
    page.mouse.move(right + 10, middle)
    page.mouse.down()
    page.mouse.move(left + 20, middle, steps=5)
    page.mouse.move(left - 4, middle, steps=2)
    page.mouse.up()


def check_delete_after_shift_home(
    check: steps.Check, page: pw.Page, where: str, editable: pw.Locator
) -> None:
    """The way the task found it: Shift+Home from the end of an item of a list, a pause, and Delete."""
    lines: t.List[str] = read_lines(editable)
    put_caret_at_end(page, editable, BY_SHIFT_HOME)
    page.keyboard.press("Shift+Home")
    wait_until_editor_holds_selection(page)
    page.keyboard.press("Delete")
    check.expect(
        f"{where} Delete over an item of a list selected by Shift+Home from its end deletes its text, and joins "
        "no item to it (lines)",
        lambda: read_lines(editable),
        empty_line(lines, BY_SHIFT_HOME),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {
                "name": "for the view beside the list",
                "description_html": to_list(LIST_LINES)
                + to_paragraphs(PARAGRAPH_LINES),
            },
            {
                "name": "for its page",
                "description_html": to_list(["apple", BY_SHIFT_HOME, "pear"]),
            },
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)

    dialog: pw.Locator = ll.open_create_dialog(page)
    page.keyboard.type("made in the dialog")
    page.keyboard.press("Enter")
    page.keyboard.type(f"- apple\n{BY_SHIFT_HOME}\npear")
    check_delete_after_shift_home(
        check, page, "in the dialog", dialog.locator(".ProseMirror")
    )
    # by its button, which saves whatever Delete did: Ctrl+Enter is a key of the editor too
    dialog.get_by_role("button", name="Save", exact=True).click()
    page_changes.wait_until_removed(dialog)
    check.expect(
        "the server stores the description of the dialog with the text deleted (lines)",
        lambda: read_stored_lines(check, project, "made in the dialog"),
        ["apple", "", "pear"],
    )

    ll.select_line(page, "for the view beside the list")
    page.keyboard.press("Enter")
    editable: pw.Locator = page.locator(
        f'#full-screen-portal [id="editor-container-{ids["for the view beside the list"]}"] .ProseMirror'
    )
    page_changes.wait_until_shown(editable)
    check_delete_after_shift_home(check, page, "in the view beside the list", editable)

    lines: t.List[str] = read_lines(editable)
    select_backwards_with_pointer(page, editable, BY_POINTER)
    wait_until_editor_holds_selection(page)
    page.keyboard.press("Delete")
    check.expect(
        "in the view beside the list Delete over an item of a list selected backwards by the pointer deletes its "
        "text (lines)",
        lambda: read_lines(editable),
        empty_line(lines, BY_POINTER),
    )

    lines = read_lines(editable)
    put_caret_at_start(page, editable, BY_SHIFT_END)
    page.keyboard.press("Shift+End")
    wait_until_editor_holds_selection(page)
    page.keyboard.press("Delete")
    check.expect(
        "in the view beside the list Delete over an item of a list selected by Shift+End from its start deletes "
        "its text (lines)",
        lambda: read_lines(editable),
        empty_line(lines, BY_SHIFT_END),
    )

    # In the three that follow, the browser tells the editor of the selection that the first key made only after
    # the second key, which comes at once: the editor still held the caret from before it.
    lines = read_lines(editable)
    put_caret_at_end(page, editable, AT_ONCE)
    page.keyboard.press("Shift+Home")
    page.keyboard.press("Delete")
    check.expect(
        "in the view beside the list Delete at once after Shift+Home in an item of a list deletes its text, and "
        "joins no item to it (lines)",
        lambda: read_lines(editable),
        empty_line(lines, AT_ONCE),
    )

    lines = read_lines(editable)
    put_caret_at_end(page, editable, PARAGRAPH_AT_ONCE)
    page.keyboard.press("Shift+Home")
    page.keyboard.press("Delete")
    check.expect(
        "in the view beside the list Delete at once after Shift+Home in a paragraph deletes its text, and joins no "
        "paragraph to it (lines)",
        lambda: read_lines(editable),
        empty_line(lines, PARAGRAPH_AT_ONCE),
    )

    lines = read_lines(editable)
    put_caret_at_start(page, editable, PARAGRAPH_BACKSPACE_AT_ONCE)
    page.keyboard.press("Shift+End")
    page.keyboard.press("Backspace")
    check.expect(
        "in the view beside the list Backspace at once after Shift+End in a paragraph deletes its text, and joins "
        "it to no paragraph (lines)",
        lambda: read_lines(editable),
        empty_line(lines, PARAGRAPH_BACKSPACE_AT_ONCE),
    )
    deleted: t.List[str] = [
        BY_SHIFT_HOME,
        BY_POINTER,
        BY_SHIFT_END,
        AT_ONCE,
        PARAGRAPH_AT_ONCE,
        PARAGRAPH_BACKSPACE_AT_ONCE,
    ]
    check.expect(
        "the server stores the description of the view beside the list with the six texts deleted (lines)",
        lambda: read_stored_lines(check, project, "for the view beside the list"),
        ["" if line in deleted else line for line in LIST_LINES + PARAGRAPH_LINES],
    )

    work_item_page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/browse/{project.identifier}-2/"
    )
    # the description, not the editor of a new comment
    editable = work_item_page.locator(".ProseMirror", has_text="apple")
    page_changes.wait_until_shown(editable)
    check_delete_after_shift_home(
        check, work_item_page, "in the work item's page", editable
    )
    check.expect(
        "the server stores the description of the work item's page with the text deleted (lines)",
        lambda: read_stored_lines(check, project, "for its page"),
        ["apple", "", "pear"],
    )
