"""
The Workspace section of the sidebar lists every entry of the workspace itself, with none of them behind a
"More"; where the window is too short for the sidebar, the sidebar scrolls as one. "Customize navigation"
lists those entries without a box to tick, and their order there is their order in the sidebar.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

SECTION: str = '[aria-label="Main sidebar"] [class~="group/sidebar-section"]'
# Whether the entry with this text lies wholly inside the part of the sidebar that scrolls.
IN_VIEW_JS: str = """
(entry) => {
  let scroller = entry.parentElement;
  while (scroller.scrollHeight <= scroller.clientHeight + 1) scroller = scroller.parentElement;
  const view = scroller.getBoundingClientRect();
  const at = entry.getBoundingClientRect();
  return at.top >= view.top && at.bottom <= view.bottom;
}
"""
# The entries under "Workspace" in the dialog, and how many of them have a box to tick.
DIALOG_JS: str = """
() => {
  const dialog = [...document.querySelectorAll('[role="dialog"]')].find((d) => d.innerText.includes('Customize navigation'));
  const block = [...dialog.querySelectorAll('h3')].find((heading) => heading.innerText.trim() === 'Workspace').parentElement;
  return [
    [...block.querySelectorAll('span.text-13')].map((name) => name.innerText.trim()),
    block.querySelectorAll('[role="checkbox"], input[type="checkbox"]').length,
  ];
}
"""


def workspace_section(page: pw.Page) -> pw.Locator:
    return page.locator(SECTION).filter(
        has=page.locator("button[aria-expanded]", has_text="Workspace")
    )


def read_entries(page: pw.Page) -> t.List[str]:
    return [
        entry.strip()
        for entry in workspace_section(page).locator("a").all_inner_texts()
    ]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "one"}])
    page: pw.Page = ll.open_list(check, account, project)
    entries: t.List[str] = ["Projects", "Wiki", "Views", "Analytics", "Archives"]

    check.expect(
        'the Workspace section lists every entry, and has no "More"',
        lambda: (
            read_entries(page),
            workspace_section(page).get_by_text("More", exact=True).count(),
        ),
        (entries, 0),
    )
    workspace_section(page).locator("a").filter(has_text="Views").click()
    check.expect(
        "a click on an entry opens its page, and the section lists the same there",
        lambda: ("views" in page.url, read_entries(page)),
        (True, entries),
    )

    page.set_viewport_size({"width": 1440, "height": 420})
    archives: pw.Locator = (
        workspace_section(page).locator("a").filter(has_text="Archives")
    )
    check.expect(
        "in a window too short for the sidebar its last entries are below what shows",
        lambda: archives.evaluate(IN_VIEW_JS),
        False,
    )
    page.mouse.move(*browser.get_point(workspace_section(page).locator("a").first))
    page.mouse.wheel(0, 2000)
    check.expect(
        "and the wheel over the sidebar brings them into view",
        lambda: archives.evaluate(IN_VIEW_JS),
        True,
    )
    page.set_viewport_size({"width": 1440, "height": 900})

    page.get_by_role("button", name="Customize navigation").first.click()
    dialog: pw.Locator = page.get_by_role("dialog").filter(
        has_text="Customize navigation"
    )
    dialog.wait_for()
    check.expect(
        '"Customize navigation" lists the entries that can be moved, without a box to tick',
        lambda: (sorted(page.evaluate(DIALOG_JS)[0]), page.evaluate(DIALOG_JS)[1]),
        (["Analytics", "Archives", "Views"], 0),
    )
    in_dialog: t.List[str] = page.evaluate(DIALOG_JS)[0]
    last: pw.FloatRect = dialog.get_by_text(in_dialog[-1], exact=True).bounding_box()
    first: pw.FloatRect = dialog.get_by_text(in_dialog[0], exact=True).bounding_box()
    # an entry is taken by the handle that stands left of its name
    browser.press_and_carry(page, (last["x"] - 40, last["y"] + last["height"] / 2))
    browser.carry_to(page, (first["x"] - 40, first["y"] + 2))
    page.mouse.up()
    moved: t.List[str] = ["Projects", "Wiki", in_dialog[-1], *in_dialog[:-1]]
    check.expect(
        "an entry dragged above another in the dialog stands there in the sidebar",
        lambda: read_entries(page),
        moved,
    )
    page.keyboard.press("Escape")
    page.reload()
    check.expect("and after a reload", lambda: read_entries(page), moved)
    page.context.close()
