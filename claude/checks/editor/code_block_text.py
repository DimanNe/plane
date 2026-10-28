"""
A code block keeps its text as it was pasted or typed, after it is saved and its work item opened again: empty lines,
leading spaces, and characters such as <, / and backticks. So it is in a description, for text pasted over the
selected text of a block from another program (plain text only), pasted at the caret from a page of the browser (HTML
and plain text), and typed at the caret; in a description changed through /api/v1/ while it is open; and in a comment,
whose code block is made by fenced text pasted as plain text.
"""

import html
import html.parser
import re
import typing as t
import uuid

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
import steps

VIEW: str = "#full-screen-portal"
DESCRIPTION: str = f"{VIEW} .ProseMirror >> nth=0"
COMMENT: str = f'{VIEW} .ProseMirror[contenteditable="true"] >> nth=-1'
CLOSE: str = 'button[aria-label="Close the peek view"]'
TEXT: str = "a a\n\nb b\n   1/ <-- asdf\n  \n    `x` *y* <b>&amp;</b>"
FENCED: str = f"```\n{TEXT}\n```"
# TEXT without its empty line and its line of spaces
WITHOUT_EMPTY_LINE: str = "a a\nb b\n   1/ <-- asdf\n    `x` *y* <b>&amp;</b>"
# The blocks of an editor from top to bottom: a code block as "code" and its text, any other as its tag and text.
BLOCKS_JS: str = """
(editor) => [...editor.children].map((block) => {
  const code = block.querySelector('pre');
  return code ? ['code', code.textContent] : [block.tagName.toLowerCase(), block.textContent];
})
"""
# Notes what every paste into the page carries: its kinds of data, sorted.
WATCH_PASTES_JS: str = """
() => {
  window.pasteKinds = [];
  document.addEventListener('paste', (event) => window.pasteKinds.push([...event.clipboardData.types].sort()), true);
}
"""
# The caret, where the page shows it: in the text of a code block, at its end.
CARET_AT_END_OF_CODE_JS: str = """
() => {
  const selection = getSelection();
  const block = selection.anchorNode?.parentElement?.closest('pre');
  return !!block && selection.isCollapsed && selection.anchorOffset === selection.anchorNode.textContent.length;
}
"""
Blocks: t.TypeAlias = t.List[t.List[str]]


class StoredBlocks(html.parser.HTMLParser):
    """The blocks of stored HTML as BLOCKS_JS reads them from an editor."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: Blocks = []
        self.depth: int = 0

    def handle_starttag(self, tag: str, attrs: t.Any) -> None:
        if self.depth == 0:
            self.blocks.append(["code" if tag == "pre" else tag, ""])
        if tag not in ("br", "img", "hr"):
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag not in ("br", "img", "hr"):
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        self.blocks[-1][1] += data


def read_stored_blocks(stored_html: str) -> Blocks:
    # /api/v1/ stores several blocks inside one div (lxml's fromstring wraps them so), which the editor shows as the
    # blocks inside it
    wrapped: t.Optional[re.Match[str]] = re.fullmatch(
        r"<div>(.*)</div>", stored_html, re.S
    )
    reader: StoredBlocks = StoredBlocks()
    reader.feed(wrapped.group(1) if wrapped else stored_html)
    return reader.blocks


def read_stored_description(check: steps.Check, project: ins.Project) -> Blocks:
    return read_stored_blocks(
        ins.read_work_items(check.instance, project)["with code"]["description_html"]
    )


def read_stored_comments(
    check: steps.Check, project: ins.Project, item_id: str
) -> t.List[ins.JSONObject]:
    return ins.call_api(
        check.instance, "GET", f"/projects/{project.id}/work-items/{item_id}/comments/"
    )["results"]


def make_description(blocks: t.Sequence[t.Tuple[str, str]]) -> str:
    """HTML of these blocks as the editor stores it, with the ids it gives its blocks: opening it changes nothing."""
    made: t.List[str] = []
    tag: str
    text: str
    for tag, text in blocks:
        attributes: str = f'data-id="{uuid.uuid4()}"'
        if tag == "code":
            made.append(
                f'<pre class="" {attributes}><code>{html.escape(text, quote=False)}</code></pre>'
            )
        else:
            kind: str = "heading" if tag == "h1" else "paragraph"
            made.append(
                f'<{tag} class="editor-{kind}-block" {attributes}>{html.escape(text, quote=False)}</{tag}>'
            )
    return "".join(made)


def copy_from_text_field(source: pw.Page, text: str) -> None:
    """Copies text as from another program: from a text field, which gives the clipboard plain text only."""
    source.bring_to_front()
    source.set_content("<textarea></textarea>")
    source.locator("textarea").fill(text)
    source.keyboard.press("Control+A")
    source.keyboard.press("Control+C")


def copy_from_page(source: pw.Page, text: str) -> None:
    """Copies text as from a page of the browser, which gives the clipboard HTML and plain text."""
    source.bring_to_front()
    source.set_content("<pre></pre>")
    source.locator("pre").evaluate("(pre, text) => { pre.textContent = text; }", text)
    source.locator("pre").click()
    source.keyboard.press("Control+A")
    source.keyboard.press("Control+C")


def put_caret_at_end_of(check: steps.Check, page: pw.Page, text_of_block: str) -> None:
    """A click on the text of a code block of one short line, whose middle is right of the text: the caret goes to the
    end of the line."""
    page.locator(DESCRIPTION).get_by_text(text_of_block, exact=True).click()
    # The click gives the editor the focus, and a moment later the editor puts back the caret it knew unless it has
    # read the click's by then (prosemirror-view's focus handler): a key pressed meanwhile could act where that was.
    check.expect_stays(
        f"a click on {text_of_block} puts the caret at its end",
        lambda: page.evaluate(CARET_AT_END_OF_CODE_JS),
        True,
    )


def open_again(page: pw.Page) -> None:
    """Closes the view beside the list, and opens the work item there again by a double click on its line."""
    page.locator(f"{VIEW} {CLOSE}").click()
    page_changes.wait_until_removed(page.locator(ll.PANEL_TITLE))
    ll.line(page, "with code").dblclick(position={"x": 6, "y": 10})
    page_changes.wait_until_shown(page.locator(ll.PANEL_TITLE))


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    before: t.List[t.Tuple[str, str]] = [
        ("h1", "Steps to follow"),
        ("p", ""),
        ("p", "some text of a first paragraph"),
        ("p", "we need to do the following"),
        ("code", WITHOUT_EMPTY_LINE),
    ]
    after: t.List[t.Tuple[str, str]] = [("p", "text after"), ("p", "")]
    blocks: t.List[t.Tuple[str, str]] = [
        *before,
        ("code", "PASTE OVER"),
        ("code", "PASTE BELOW"),
        ("code", "TYPE ABOVE"),
        *after,
    ]
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [{"name": "with code", "description_html": make_description(blocks)}],
    )
    expected: Blocks = [
        *[list(block) for block in before],
        ["code", FENCED],
        ["code", f"PASTE BELOW\n{TEXT}"],
        ["code", f"{TEXT}\nTYPE ABOVE"],
        *[list(block) for block in after],
    ]
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    source: pw.Page = page.context.new_page()
    page.evaluate(WATCH_PASTES_JS)
    description: pw.Locator = page.locator(DESCRIPTION)

    ll.line(page, "with code").dblclick(position={"x": 6, "y": 10})
    page_changes.wait_until_shown(description.get_by_text("PASTE BELOW", exact=True))
    copy_from_page(source, TEXT)
    page.bring_to_front()
    put_caret_at_end_of(check, page, "PASTE BELOW")
    page.keyboard.press("Enter")
    page.keyboard.press("Control+V")
    # ↓ at the end of a code block puts the caret at the start of the next one
    page.keyboard.press("ArrowDown")
    page.keyboard.type(f"{TEXT}\n")
    copy_from_text_field(source, FENCED)
    page.bring_to_front()
    # a triple click selects the whole text of the block
    description.get_by_text("PASTE OVER", exact=True).click(click_count=3)
    page_changes.wait_until_true(
        page, "() => getSelection().toString() === 'PASTE OVER'"
    )
    page.keyboard.press("Control+V")
    check.expect(
        "the pastes carry HTML and plain text (from a page), and plain text only (from a text field)",
        lambda: page.evaluate("() => window.pasteKinds"),
        [["text/html", "text/plain"], ["text/plain"]],
    )
    check.expect(
        "the code blocks show the text as pasted and typed, and the blocks around them stay",
        lambda: description.evaluate(BLOCKS_JS),
        expected,
    )
    check.expect(
        "the server stores the description so",
        lambda: read_stored_description(check, project),
        expected,
    )

    open_again(page)
    # Read as markdown, stored HTML that starts with a block's tag was kept as it is up to the first empty line: a code
    # block above it kept its text, and the blocks from there on did not.
    check.expect(
        "opened again, a code block without an empty line, above the others, keeps its text (it always did)",
        lambda: [
            block for block in description.evaluate(BLOCKS_JS) if block[0] == "code"
        ][0],
        ["code", WITHOUT_EMPTY_LINE],
    )
    check.expect(
        "and the code blocks with empty lines show their text as it was, and the blocks after them stay",
        lambda: description.evaluate(BLOCKS_JS),
        expected,
    )
    check.expect_stays(
        "and the server keeps them: opening the work item stores nothing else",
        lambda: read_stored_description(check, project),
        expected,
    )

    changed: t.List[t.Tuple[str, str]] = [
        ("h1", "Steps to follow"),
        ("p", "as an agent wrote them"),
        ("code", TEXT),
        ("p", ""),
    ]
    ins.call_api(
        check.instance,
        "PATCH",
        f"/projects/{project.id}/work-items/{ids['with code']}/",
        {"description_html": make_description(changed)},
    )
    check.expect(
        "a description changed through /api/v1/ shows in the open view with its code block as stored",
        lambda: description.evaluate(BLOCKS_JS),
        [list(block) for block in changed],
    )
    check.expect_stays(
        "and the server keeps the code block so",
        lambda: read_stored_description(check, project),
        [list(block) for block in changed],
    )

    copy_from_text_field(source, FENCED)
    page.bring_to_front()
    page.locator(COMMENT).click()
    page.keyboard.type("like this:")
    page.keyboard.press("Enter")
    page.keyboard.press("Control+V")
    page.keyboard.press("Control+Enter")
    comment: Blocks = [["p", "like this:"], ["code", TEXT]]
    check.expect(
        "fenced text pasted into a comment makes a code block, and Ctrl+Enter sends it so (stored)",
        lambda: [
            read_stored_blocks(stored["comment_html"])
            for stored in read_stored_comments(check, project, ids["with code"])
        ],
        [comment],
    )
    comment_id: str = read_stored_comments(check, project, ids["with code"])[0]["id"]
    shown_comment: pw.Locator = page.locator(
        f'{VIEW} [id="editor-container-{comment_id}"] .ProseMirror'
    )
    check.expect(
        "the comment shows the code block as pasted",
        lambda: shown_comment.evaluate(BLOCKS_JS),
        comment,
    )
    open_again(page)
    check.expect(
        "opened again, the comment shows it so",
        lambda: shown_comment.evaluate(BLOCKS_JS),
        comment,
    )
    source.close()
    page.context.close()
