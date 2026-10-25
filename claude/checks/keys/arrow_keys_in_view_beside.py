"""
While the caret is in the title or the description of the work item open in the view beside the list, the arrow keys
move the caret and nothing else: the same work item stays open, and the list's selection stays where it is. ↑ goes
up the description line by line, from its first line to the end of the title, and in the title to its start; ↓ goes
down the description line by line and stays on its last line, and in the title goes to its end. So it is with a line
above and a line below the open work item's, after a double click on its line with the pointer passing over those
lines on its way to the view, and after the view went on to a sub-work item, whose line is not the selected one.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

LINES_OF_DESCRIPTION: t.List[str] = [
    "first line",
    "second line",
    "third line",
    "last line",
]
# Where the caret is: at the start or the end of the title of the view, elsewhere in it, on a line of the description
# of the work item with this id, or else the element that has the focus.
CARET_JS: str = """
([id, titleSelector]) => {
  const element = document.activeElement;
  const title = document.querySelector(titleSelector);
  if (element && element === title) {
    if (title.selectionStart !== title.selectionEnd) return 'over a part of the title';
    if (title.selectionStart === 0) return 'at the start of the title';
    return title.selectionStart === title.value.length ? 'at the end of the title' : 'in the title';
  }
  const description = document.querySelector(`#full-screen-portal [id="editor-container-${id}"] .ProseMirror`);
  if (!element || element !== description) return element?.tagName ?? null;
  const node = getSelection().focusNode;
  const line = (node instanceof Element ? node : node?.parentElement)?.closest('p');
  return line ? `on the line "${line.textContent}"` : 'in the description, on no line';
}
"""


def read_caret(page: pw.Page, work_item_id: str) -> t.Optional[str]:
    return page.evaluate(CARET_JS, [work_item_id, ll.PANEL_TITLE])


def read_lines_of_description(page: pw.Page, work_item_id: str) -> t.List[str]:
    return page.locator(
        f'#full-screen-portal [id="editor-container-{work_item_id}"] p'
    ).all_inner_texts()


def get_point_on_line(page: pw.Page, title: str) -> t.Tuple[float, float]:
    """A point of the line with this title, left of the view beside the list."""
    box: t.Optional[pw.FloatRect] = ll.line(page, title).bounding_box()
    assert box is not None
    return box["x"] + 100, box["y"] + box["height"] / 2


def click_on_line_of_description(
    page: pw.Page, work_item_id: str, text: str, is_at_end: bool
) -> None:
    """A click at the start or the end of a line of the description; the pointer goes there as a hand moves it."""
    box: t.Optional[pw.FloatRect] = (
        page.locator(f'#full-screen-portal [id="editor-container-{work_item_id}"] p')
        .filter(has_text=text)
        .bounding_box()
    )
    assert box is not None
    x: float = box["x"] + (box["width"] - 2 if is_at_end else 1)
    y: float = box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=10)
    page.mouse.click(x, y)


def press_and_expect(
    check: steps.Check,
    page: pw.Page,
    situation: str,
    key: str,
    caret: str,
    work_item_id: str,
    open_and_selected: t.Tuple[str, t.List[str]],
) -> None:
    """The key moves the caret, and then nothing more happens: the view and the list's selection stay."""
    page.keyboard.press(key)
    check.expect(
        f"{situation}: {key} puts the caret {caret}",
        lambda: read_caret(page, work_item_id),
        caret,
    )
    check.expect_stays(
        f"{situation}: after {key} the caret stays there, the same work item stays open and the list's selection "
        "stays (caret, open work item, selected lines)",
        lambda: (
            read_caret(page, work_item_id),
            ll.read_panel(page),
            ll.read_selected(page),
        ),
        (caret, *open_and_selected),
    )


def go_through_with_arrow_keys(
    check: steps.Check,
    page: pw.Page,
    situation: str,
    work_item_id: str,
    open_and_selected: t.Tuple[str, t.List[str]],
) -> None:
    """From the end of the description's last line up to the title, then from the start of its first line down to
    its last line and once more."""
    first, *middle, last = LINES_OF_DESCRIPTION

    def press(key: str, caret: str) -> None:
        press_and_expect(
            check, page, situation, key, caret, work_item_id, open_and_selected
        )

    line: str
    for line in reversed([first, *middle]):
        press("ArrowUp", f'on the line "{line}"')
    press("ArrowUp", "at the end of the title")
    press("ArrowUp", "at the start of the title")
    press("ArrowDown", "at the end of the title")
    click_on_line_of_description(page, work_item_id, first, is_at_end=False)
    check.expect(
        f"{situation}: a click at the start of the description puts the caret on its first line",
        lambda: read_caret(page, work_item_id),
        f'on the line "{first}"',
    )
    for line in [*middle, last]:
        press("ArrowDown", f'on the line "{line}"')
    press("ArrowDown", f'on the line "{last}"')


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    description: str = "".join(f"<p>{line}</p>" for line in LINES_OF_DESCRIPTION)
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "above"},
            {"name": "parent"},
            {"name": "edited", "parent": "parent", "description_html": description},
            {"name": "below"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    check.expect(
        "the lines: the open work item's has one above it and one below it",
        lambda: ll.read_titles(page),
        ["above", "parent", "edited", "below"],
    )

    situation: str = "after a double click on the line"
    ll.line(page, "edited").locator("p").first.dblclick()
    check.expect(
        f"{situation}: its work item is open beside the list with its description, and its line is selected "
        "(open work item, its description, selected lines)",
        lambda: (
            ll.read_panel(page),
            read_lines_of_description(page, ids["edited"]),
            ll.read_selected(page),
        ),
        ("edited", LINES_OF_DESCRIPTION, ["edited"]),
    )
    # On its way to the view the pointer passes over the line below and the line above, and enters the view from the
    # line above, to the right of it.
    page.mouse.move(*get_point_on_line(page, "below"), steps=5)
    x, y = get_point_on_line(page, "parent")
    page.mouse.move(x, y, steps=5)
    view_title: t.Optional[pw.FloatRect] = page.locator(ll.PANEL_TITLE).bounding_box()
    assert view_title is not None
    page.mouse.move(view_title["x"] + 10, y, steps=5)
    click_on_line_of_description(
        page, ids["edited"], LINES_OF_DESCRIPTION[-1], is_at_end=True
    )
    check.expect(
        f"{situation}: a click at the end of the description puts the caret on its last line",
        lambda: read_caret(page, ids["edited"]),
        f'on the line "{LINES_OF_DESCRIPTION[-1]}"',
    )
    go_through_with_arrow_keys(
        check, page, situation, ids["edited"], ("edited", ["edited"])
    )

    situation = "in a sub-work item that the view went on to"
    ll.line(page, "parent").locator("p").first.dblclick()
    check.expect(
        "a double click on the line of the parent opens it",
        lambda: (ll.read_panel(page), ll.read_selected(page)),
        ("parent", ["parent"]),
    )
    page.locator("#full-screen-portal").get_by_text("edited", exact=True).click()
    check.expect(
        f"{situation}: a click on the sub-work item in the view opens it there, and the parent's line stays "
        "selected (open work item, its description, selected lines)",
        lambda: (
            ll.read_panel(page),
            read_lines_of_description(page, ids["edited"]),
            ll.read_selected(page),
        ),
        ("edited", LINES_OF_DESCRIPTION, ["parent"]),
    )
    click_on_line_of_description(
        page, ids["edited"], LINES_OF_DESCRIPTION[-1], is_at_end=True
    )
    check.expect(
        f"{situation}: a click at the end of the description puts the caret on its last line",
        lambda: read_caret(page, ids["edited"]),
        f'on the line "{LINES_OF_DESCRIPTION[-1]}"',
    )
    go_through_with_arrow_keys(
        check, page, situation, ids["edited"], ("edited", ["parent"])
    )
    page.context.close()
