"""
The dialog of a new work item has no heading: under the project stand the title and the description as one text,
without a frame around either, starting at one left edge, the title in a larger size, the description saying "Add
description" until it has text. For screen readers the dialog
is still named "Create new work item". It fades and grows in as it opens, as the other dialogs do.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# The opacity and the scale of a dialog with the title of a work item, in every frame the page draws from now on,
# until a frame shows it whole. A window without a frame rate limit draws many frames in one opening.
RECORD_OPENING_JS: str = """
() => {
  window.__openingFrames = [];
  window.__isOpened = false;
  const record = () => {
    const dialog = [...document.querySelectorAll('[role="dialog"]')].find((d) => d.querySelector('input[name="name"]'));
    if (dialog) {
      const style = getComputedStyle(dialog);
      window.__openingFrames.push([Number(style.opacity), style.scale]);
      if (style.opacity === '1' && style.scale === 'none') {
        window.__isOpened = true;
        return;
      }
    }
    requestAnimationFrame(record);
  };
  requestAnimationFrame(record);
}
"""
# The elements between the dialog and the title, and between the dialog and the description, that draw a border.
FRAMES_JS: str = """
() => {
  const dialog = [...document.querySelectorAll('[role="dialog"]')].find((d) => d.querySelector('input[name="name"]'));
  const framed = (start) => {
    const found = [];
    for (let e = start; e && e !== dialog; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (parseFloat(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none' && !s.borderTopColor.endsWith(', 0)')
          && s.borderTopColor !== 'transparent')
        found.push(e.tagName.toLowerCase());
    }
    return found;
  };
  return [framed(dialog.querySelector('input[name="name"]')), framed(dialog.querySelector('.ProseMirror'))];
}
"""
LEFT_EDGES_JS: str = """
() => {
  const dialog = [...document.querySelectorAll('[role="dialog"]')].find((d) => d.querySelector('input[name="name"]'));
  const title = dialog.querySelector('input[name="name"]').getBoundingClientRect();
  const text = dialog.querySelector('.ProseMirror p').getBoundingClientRect();
  return [title.left, text.left, parseFloat(getComputedStyle(dialog.querySelector('input[name="name"]')).fontSize),
          parseFloat(getComputedStyle(dialog.querySelector('.ProseMirror p')).fontSize)];
}
"""
# The size in which the element that names the dialog is drawn.
NAME_DRAWN_JS: str = """
() => {
  const dialog = [...document.querySelectorAll('[role="dialog"]')].find((d) => d.querySelector('input[name="name"]'));
  const name = document.getElementById(dialog.getAttribute('aria-labelledby'));
  const r = name.getBoundingClientRect();
  return [name.textContent, r.width > 1 && r.height > 1];
}
"""


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "one"}])
    page: pw.Page = ll.open_list(check, account, project)

    page.evaluate(RECORD_OPENING_JS)
    dialog: pw.Locator = ll.open_create_dialog(page)
    page.wait_for_function("() => window.__isOpened")
    frames: t.List[t.List[t.Any]] = page.evaluate("() => window.__openingFrames")
    check.expect(
        "the dialog fades and grows in: its first frame shows it nearly transparent and smaller, and it takes frames to be "
        "whole (first frame, frames until whole)",
        lambda: (frames[0][0] < 0.5 and frames[0][1] != "none", len(frames) > 2),
        (True, True),
        timeout=0,
    )
    check.expect(
        'no heading is drawn in it; it is named "Create new work item" for screen readers (name, drawn)',
        lambda: page.evaluate(NAME_DRAWN_JS),
        ["Create new work item", False],
    )
    dialog.locator(".ProseMirror p").first.wait_for()
    check.expect(
        'until something is typed into it, the description says "Add description"',
        lambda: dialog.locator(".ProseMirror p").first.get_attribute(
            "data-placeholder"
        ),
        "Add description",
    )
    check.expect(
        "neither the title nor the description has a frame around it (framed elements of each)",
        lambda: page.evaluate(FRAMES_JS),
        [[], []],
    )
    left_of_title: float
    left_of_text: float
    size_of_title: float
    size_of_text: float
    left_of_title, left_of_text, size_of_title, size_of_text = page.evaluate(
        LEFT_EDGES_JS
    )
    check.expect_at_most(
        "the title and the description start at one left edge (pixels apart)",
        abs(left_of_title - left_of_text),
        1,
    )
    check.expect_at_least(
        "and the title is drawn larger than the description (pixels of font size more)",
        size_of_title - size_of_text,
        2,
    )
