"""
The List layout of a project's work items: what a person does there, and what the page shows of it.

A line is found by the title of its work item, which a check chooses, never by its place or by a number that
the instance gave. What is read is what is drawn: the lines in their order with their group and level, the
line that is drawn as selected, what has the focus.
"""

import re
import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import page_changes
import steps

LINE: str = '[class~="group/list-block"]'
PANEL_TITLE: str = '#full-screen-portal textarea[placeholder="Work item title"]'
MESSAGE: str = '[aria-label="Notifications"] > *'
CREATE_DIALOG: str = '[role="dialog"]:has(button:has-text("Discard"))'
# Whether the caret is in the description of the work item with this id, in the view beside the list.
CARET_IN_DESCRIPTION_JS: str = """
(id) => !!document.activeElement?.classList.contains('ProseMirror')
  && !!document.activeElement.closest(`#full-screen-portal [id="editor-container-${id}"]`)
"""
QUESTION: str = '[role="dialog"]:has-text("Are you sure"), [role="alertdialog"]:has-text("Are you sure")'
# An open menu of a property of a work item (state, priority, ...). A menu that has closed stays in the page, marked
# closed, while it fades out, which takes longer than a step that follows at once; it is not open, and neither is
# the picture of a menu that a state's letter leaves.
PROPERTY_MENU: str = "[data-select-popup]:not([data-closed], .menu-choice-picture, .menu-choice-picture *)"
# pixels a level of sub-work items is indented by
INDENT: int = 24

# A line that goes to another place is carried there as a picture of itself, which is not a line of the list.
IS_OF_THE_LIST_JS: str = (
    "const isOfTheList = (line) => !line.closest('.new-work-item-morph');"
)
# The lines of the list from top to bottom: the group they stand in, their level, their title.
LINES_JS: str = """
(indent) => [...document.querySelectorAll('[class~="group/list-block"]')].filter(isOfTheList).map((line) => {
  const indented = line.querySelector('[style*="margin-left"]');
  let group = line;
  while (group && !group.querySelector(':scope > div [class~="group/list-header"]')) group = group.parentElement;
  return [
    group?.querySelector('[class~="group/list-header"] .truncate')?.textContent.trim() ?? null,
    indented ? Math.round(parseFloat(indented.style.marginLeft) / indent) : 0,
    line.querySelector('p')?.textContent ?? line.querySelector('input')?.value ?? '',
  ];
})
"""
SELECTED_JS: str = """
() => [...document.querySelectorAll('[class~="group/list-block"]')]
  .filter((line) => isOfTheList(line) && line.className.includes('bg-layer-transparent-selected'))
  .map((line) => line.querySelector('p')?.textContent ?? line.querySelector('input')?.value ?? '')
"""


# The lines the page points out by a tint of their background.
TINTED_JS: str = """
() => [...document.querySelectorAll('[class~="group/list-block"]')]
  .filter((line) => isOfTheList(line)
    && line.getAnimations().some((animation) => animation.effect.getKeyframes().some((frame) => frame.backgroundColor)))
  .map((line) => line.querySelector('p')?.textContent ?? '')
"""
# The headers of the groups from top to bottom: name, the count beside it, whether it offers the "+".
HEADERS_JS: str = """
() => [...document.querySelectorAll('[class~="group/list-header"]')].map((header) => [
  header.querySelector('.truncate').textContent.trim(),
  Number(header.querySelector('.text-tertiary').textContent),
  header.querySelector('button[aria-label="New work item"]') !== null,
])
"""
# The input that the "+" of a group opens: the group it stands in, what it holds, whether the caret is in it.
INPUT_OF_GROUP_JS: str = """
() => {
  const input = document.querySelector('form input[name="name"]');
  if (!input || input.closest('[role="dialog"]')) return null;
  let group = input;
  while (!group.querySelector(':scope > div [class~="group/list-header"]')) group = group.parentElement;
  const header = group.querySelector('[class~="group/list-header"]');
  return [
    header.querySelector('.truncate').textContent.trim(),
    input.value,
    input === document.activeElement,
    Math.round(input.getBoundingClientRect().top - header.getBoundingClientRect().bottom) < 20,
  ];
}
"""


def open_list(
    check: steps.Check,
    account: ins.Account,
    project: ins.Project,
    *,
    origin: t.Optional[str] = None,
    **display_filters: t.Any,
) -> pw.Page:
    """The project's work items in the List layout, in the manual order and grouped by state unless told
    otherwise, with its first line drawn; at `origin` when given (see browser.open_page)."""
    ins.set_display(
        check.instance,
        account,
        project,
        **{
            "layout": "list",
            "group_by": "state",
            "order_by": "sort_order",
            "sub_issue": True,
            "show_empty_groups": True,
            **display_filters,
        },
    )
    page: pw.Page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/projects/{project.id}/issues/",
        origin=origin,
    )
    page_changes.wait_until_shown(page.locator(LINE).first)
    return page


def line(page: pw.Page, title: str) -> pw.Locator:
    return page.locator(LINE).filter(has=page.get_by_text(title, exact=True)).first


def line_in_group(page: pw.Page, group: str, title: str) -> pw.Locator:
    """The line with this title in a group, where a work item has lines in several."""
    return (
        group_header(page, group)
        .locator("xpath=../..")
        .locator(LINE)
        .filter(has=page.get_by_text(title, exact=True))
        .first
    )


def read_lines(page: pw.Page) -> t.List[t.List[t.Any]]:
    return page.evaluate(
        f"(indent) => {{ {IS_OF_THE_LIST_JS} return ({LINES_JS})(indent); }}", INDENT
    )


def read_lines_in_another_group(page: pw.Page) -> t.List[t.List[t.Any]]:
    """The lines drawn dimmed, as a group draws the parent of its work items that stands in another group: the
    group they are drawn in, and their title."""
    return [
        [group, title]
        for (group, _, title), is_dimmed in zip(
            read_lines(page),
            page.evaluate(
                f"""() => {{ {IS_OF_THE_LIST_JS}
                  return [...document.querySelectorAll('{LINE}')].filter(isOfTheList)
                    .map((line) => Number(getComputedStyle(line).opacity) < 1); }}"""
            ),
        )
        if is_dimmed
    ]


def read_titles(page: pw.Page) -> t.List[str]:
    return [title for _, _, title in read_lines(page)]


def read_selected(page: pw.Page) -> t.List[str]:
    return page.evaluate(f"() => {{ {IS_OF_THE_LIST_JS} return ({SELECTED_JS})(); }}")


def select_line(page: pw.Page, title: str) -> None:
    """A click on the line where it holds no control: in its left padding, before the id."""
    target: pw.Locator = line(page, title)
    target.click(position={"x": 6, "y": 10})


def read_menu_of_line(page: pw.Page, title: str) -> t.List[str]:
    """The entries of the menu that a right click on the line opens; the menu is closed again."""
    target: pw.Locator = line(page, title)
    target.click(button="right", position={"x": 6, "y": 10})
    page_changes.wait_until_shown(page.get_by_role("menu"))
    entries: t.List[str] = [
        entry.inner_text().strip() for entry in page.get_by_role("menuitem").all()
    ]
    page.keyboard.press("Escape")
    page_changes.wait_until_removed(page.get_by_role("menu"))
    return entries


def read_messages(page: pw.Page) -> t.List[str]:
    """The texts of the messages the page shows in its corner, each on one line."""
    return [
        " | ".join(part for part in message.inner_text().split("\n") if part.strip())
        for message in page.locator(MESSAGE).all()
    ]


def close_message(page: pw.Page) -> None:
    """Closes the one message the page shows as a person who has read it: by the button it offers under the
    pointer."""
    page.locator(MESSAGE).hover()
    # by its label: the page keeps a message of a failure out of the tree of roles
    page.locator(MESSAGE).get_by_label("Close").click()
    page_changes.wait_until_removed(page.locator(MESSAGE))


def open_create_dialog(page: pw.Page, keys: str = "ni") -> pw.Locator:
    """N then I, or N then C for a sub-work item of the selected line; the dialog with the caret in its title."""
    dialog: pw.Locator = page.locator(CREATE_DIALOG)
    # The page loses keys pressed while such a dialog is still there, also one that was just saved and is about
    # to close, which takes until the server has answered: a fault of the page that a person who types fast meets.
    page_changes.wait_until_removed(dialog)
    key: str
    for key in keys:
        page.keyboard.press(key)
    page_changes.wait_until_shown(dialog)
    page_changes.wait_until_true(page, "() => document.activeElement?.name === 'name'")
    return dialog


def make_with_keys(
    check: steps.Check, project: ins.Project, page: pw.Page, title: str
) -> t.Tuple[t.List[t.Any], ins.JSONObject]:
    """N I, what the dialog shows, and the work item stored after its title is typed and Ctrl+Enter pressed: the
    dialog closes when the server has answered."""
    # What the open dialog of a new work item shows as its state, priority and labels.
    SHOWN_JS: str = """
() => {
  const dialog = [...document.querySelectorAll('[role="dialog"]')].find((d) => d.querySelector('input[name="name"]'));
  const said = (id) => dialog?.querySelector(`[data-testid="${id}"]`)?.innerText.trim() ?? null;
  return [said('create-work-item-state-select'), said('create-work-item-priority-select'), said('create-work-item-label-select')];
}
"""
    open_create_dialog(page)
    shown: t.List[t.Any] = page.evaluate(SHOWN_JS)
    page.keyboard.type(title)
    page.keyboard.press("Control+Enter")
    page_changes.wait_until_removed(page.locator(CREATE_DIALOG))
    return shown, ins.read_work_items(check.instance, project)[title]


def choose_option(page: pw.Page, button: pw.Locator, option: str) -> None:
    """Opens the menu of a button, takes the option with this text, and waits until the menu has closed and
    given the focus back to its button: until then a key that follows goes nowhere."""
    button.click()
    page.get_by_role("option").filter(has_text=option).first.click()
    page_changes.wait_until_removed(page.get_by_role("option").first)
    page_changes.wait_until_true(
        page,
        "(button) => document.activeElement === button",
        arg=button.element_handle(),
    )


def group_header(page: pw.Page, name: str) -> pw.Locator:
    """The header of a group, as wide as the list."""
    return page.locator('[id^="list_group_header_"]').filter(
        has=page.get_by_text(name, exact=True)
    )


def create_work_item(page: pw.Page, title: str, keys: str = "ni") -> None:
    """Opens the dialog with the keys, gives the title, and saves with Ctrl+Enter."""
    open_create_dialog(page, keys)
    page.keyboard.type(title)
    page.keyboard.press("Control+Enter")


def read_tinted(page: pw.Page) -> t.List[str]:
    return page.evaluate(f"() => {{ {IS_OF_THE_LIST_JS} return ({TINTED_JS})(); }}")


def read_groups(page: pw.Page) -> t.List[t.List[t.Any]]:
    """The groups from top to bottom: name, the count beside it, how many lines it shows, whether its header
    offers the "+"."""
    shown: t.List[str] = [group for group, _, _ in read_lines(page)]
    return [
        [name, count, shown.count(name), has_plus]
        for name, count, has_plus in page.evaluate(HEADERS_JS)
    ]


def read_input_of_group(page: pw.Page) -> t.Optional[t.List[t.Any]]:
    return page.evaluate(INPUT_OF_GROUP_JS)


def plus_of_group(page: pw.Page, name: str) -> pw.Locator:
    return group_header(page, name).get_by_role("button", name="New work item")


def open_input_of_group(page: pw.Page, name: str) -> None:
    """A click on the "+" of a group; returns when the caret is in the input it opens."""
    plus_of_group(page, name).click()
    page_changes.wait_until_true(page, "() => document.activeElement?.name === 'name'")


def read_description(check: steps.Check, project: ins.Project, name: str) -> str:
    """The text the server has stored as the description of the work item called `name`."""
    html: str = (
        ins.read_work_items(check.instance, project)[name].get("description_html") or ""
    )
    return re.sub(r"<[^>]+>", "", html).replace("&nbsp;", " ")


def read_comments(
    check: steps.Check, project: ins.Project, item_id: str
) -> t.List[t.List[str]]:
    """The comments of a work item, oldest first, each as its paragraphs."""
    found: t.List[ins.JSONObject] = ins.call_api(
        check.instance, "GET", f"/projects/{project.id}/work-items/{item_id}/comments/"
    )["results"]
    return [
        [
            re.sub(r"<[^>]+>", "", paragraph)
            for paragraph in re.findall(r"<p[^>]*>(.*?)</p>", comment["comment_html"])
        ]
        for comment in sorted(found, key=lambda comment: comment["created_at"])
    ]


def read_panel(page: pw.Page) -> t.Optional[str]:
    """The title in the work item view beside the list; None while it is closed."""
    title: pw.Locator = page.locator(PANEL_TITLE)
    return title.first.input_value() if title.count() else None


def read_focus(page: pw.Page) -> str:
    """What has the focus, as a person would name it: "page", or the control's kind and label."""
    return page.evaluate(
        """() => {
          const e = document.activeElement;
          if (!e || e === document.body) return 'page';
          return e.tagName.toLowerCase() + ' ' + (e.getAttribute('aria-label') ?? e.getAttribute('name') ?? e.getAttribute('placeholder') ?? '');
        }"""
    )


# What the list draws for a line that is carried over it: the thick line between two lines or at the end of a
# group, the line that would take the carried one in, the group it would go to.
DROP_MARKS_JS: str = """
() => {
  const list = document.querySelector('.vertical-scrollbar.scrollbar-lg');
  const titleOf = (place) => place.querySelector('p')?.textContent ?? '';
  const groupOf = (header) => header.querySelector('.truncate')?.textContent.trim();
  const marks = [];
  for (const line of list.querySelectorAll('div.bg-accent-primary')) {
    const box = line.getBoundingClientRect();
    if (box.width === 0) continue;
    const place = line.closest('[id^="issue_"]')?.getBoundingClientRect();
    const style = getComputedStyle(line);
    let group = line;
    while (!place && !group.querySelector(':scope > div [class~="group/list-header"]')) group = group.parentElement;
    marks.push({
      line: !place ? 'at the end of' : box.top + box.height / 2 < place.top + place.height / 2 ? 'above' : 'below',
      at: place ? titleOf(line.closest('[id^="issue_"]')) : groupOf(group),
      from: Math.round(box.left),
      to: Math.round(box.right),
      thick: box.height,
      solid: style.opacity === '1' && !/rgba|\\//.test(style.backgroundColor),
    });
  }
  for (const place of list.querySelectorAll('[id^="issue_"]'))
    if (place.className.includes('outline-accent-strong')) marks.push({ into: titleOf(place) });
  for (const header of list.querySelectorAll('[id^="list_group_header_"]'))
    if (header.className.includes('outline-accent-strong')) marks.push({ group: groupOf(header) });
  return marks;
}
"""


def carry(page: pw.Page, carried: pw.Locator) -> None:
    """Takes a line by its left padding, where it holds no control, and begins to drag it."""
    box: t.Optional[pw.FloatRect] = carried.bounding_box()
    assert box is not None
    browser.press_and_carry(page, (box["x"] + 6, box["y"] + box["height"] / 2))


def carry_line(page: pw.Page, title: str) -> None:
    carry(page, line(page, title))


def hold_over(page: pw.Page, target: pw.Locator, down: float) -> None:
    """Brings the carried line over an element, at a part of its height."""
    browser.carry_to(page, browser.get_point(target, across=0.3, down=down))


def drop_on(
    page: pw.Page, carried: pw.Locator, target: pw.Locator, down: float
) -> None:
    carry(page, carried)
    hold_over(page, target, down)
    page.mouse.up()


def read_drop_marks(page: pw.Page) -> t.List[t.Dict[str, t.Any]]:
    return page.evaluate(DROP_MARKS_JS)


Frame: t.TypeAlias = t.Dict[str, t.Any]
# A line that comes to a new place is carried there by a box. From now on, for every frame the page draws: the
# box (where it is drawn, where it was sent to, whether it is set to go out on its way), the dialog of a new
# work item, the line with this title (where it is, its group, whether its place is shown, whether it is tinted
# and wholly in view), a line that the change does not concern, and how far the list is scrolled.
RECORD_BOX_JS: str = """
([title, still]) => {
  const frames = [];
  window.__box = { frames, stopped: false, transitions: window.__box?.transitions ?? 0 };
  if (!window.__box_watches_transitions && document.startViewTransition) {
    const start = document.startViewTransition.bind(document);
    document.startViewTransition = (update) => { window.__box.transitions += 1; return start(update); };
    window.__box_watches_transitions = true;
  }
  const rect = (element) => { const r = element.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; };
  const lineOf = (name) => [...document.querySelectorAll('[class~="group/list-block"]')]
    .find((line) => !line.closest('.new-work-item-morph') && line.querySelector('p')?.textContent === name);
  const groupOf = (line) => {
    let group = line;
    while (!group.querySelector(':scope > div [class~="group/list-header"]')) group = group.parentElement;
    return group.querySelector('[class~="group/list-header"] .truncate').textContent.trim();
  };
  const record = () => {
    const boxes = document.querySelectorAll('.new-work-item-morph');
    const box = boxes[0];
    const dialog = [...document.querySelectorAll('[role="dialog"]')]
      .find((d) => !d.closest('.new-work-item-morph') && d.querySelector('input[name="name"]'));
    const line = lineOf(title);
    const stillLine = lineOf(still);
    const list = document.querySelector('.vertical-scrollbar.scrollbar-lg');
    const view = list.getBoundingClientRect();
    const at = line?.getBoundingClientRect();
    frames.push({
      boxes: boxes.length,
      box: box ? rect(box) : null,
      sentTo: box ? ['left', 'top', 'width', 'height'].map((side) => parseFloat(box.style[side])) : null,
      goesOut: box ? box.getAnimations().some((a) => a.effect.getKeyframes().some((frame) => 'opacity' in frame)) : null,
      dialog: dialog ? rect(dialog) : null,
      line: line ? rect(line) : null,
      group: line ? groupOf(line) : null,
      shown: line ? Number(getComputedStyle(line.closest('[id^="issue_"]')).opacity) : null,
      tinted: line ? line.getAnimations().some((a) => a.effect.getKeyframes().some((frame) => frame.backgroundColor)) : null,
      inView: line ? at.top >= view.top && at.bottom <= view.bottom + 1 : null,
      still: stillLine ? stillLine.getBoundingClientRect().top : null,
      scrolled: list.scrollTop,
      view: [view.top, view.bottom],
    });
    if (!window.__box.stopped) requestAnimationFrame(record);
  };
  requestAnimationFrame(record);
}
"""
# what of a box would still be on the page: the box itself, an animation of it, a part of the page it disabled
LEFT_OF_BOX_JS: str = """
() => [
  document.querySelectorAll('.new-work-item-morph').length,
  document.getAnimations().filter((a) => a.effect?.target?.closest?.('.new-work-item-morph')).length,
  document.querySelectorAll('[inert]').length,
]
"""


def record_box(page: pw.Page, title: str, still: t.Optional[str] = None) -> None:
    """Begins to write down every frame of the box that carries the line with this title, and of a line that
    has to stay where it is."""
    page.evaluate(RECORD_BOX_JS, [title, still])


# whether a box has come and gone, and the line is shown where it has to be drawn in the end
BOX_HAS_GONE_JS: str = """
(isLineDrawn) => {
  const frames = window.__box.frames;
  const last = frames[frames.length - 1];
  return frames.some((frame) => frame.box) && !last.box && (isLineDrawn ? last.shown === 1 : last.shown !== 0);
}
"""


def stop_recording_box(page: pw.Page) -> t.List[Frame]:
    page.evaluate("window.__box.stopped = true")
    return page.evaluate("window.__box.frames")


def read_box_frames(page: pw.Page, is_line_drawn: bool = True) -> t.List[Frame]:
    """The frames written down, once the box has come and gone; `is_line_drawn` tells whether the list draws
    the line at its new place, which it does not where that place is out of view."""
    # FOR_REVIEWER: read every frame by Playwright, and not on a change of the page (page_changes.py): what is read
    # is what the recorder writes in its own frame callbacks, which no change of the page tells of.
    page.wait_for_function(BOX_HAS_GONE_JS, arg=is_line_drawn)
    return stop_recording_box(page)


def read_left_of_box(page: pw.Page) -> t.List[int]:
    """What boxes left on the page and how many view transitions of the browser were started: all zero."""
    return page.evaluate(LEFT_OF_BOX_JS) + [page.evaluate("window.__box.transitions")]


def get_distance(a: t.Sequence[float], b: t.Sequence[float]) -> float:
    """The largest difference of left, top, width and height between two rectangles, in pixels."""
    return round(max(abs(x - y) for x, y in zip(a, b)), 2)
