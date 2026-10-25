"""
The menus of a line and of the list's header scroll only when their options do not fit: where they fit, a
menu shows all of them without a scroll bar, one under the other with neither overlap nor gap. In a menu that
scrolls, the option the arrow keys reach is always inside what the menu shows.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
import steps

# Of the open menu: how far its list can scroll, the gaps between its options (negative where they overlap),
# and whether the option the keys have reached lies wholly inside what the list shows.
MENU_JS: str = """
() => {
  const options = [...document.querySelectorAll('[role="option"]')].filter((o) => o.getClientRects().length);
  let list = options[0].parentElement;
  while (list && getComputedStyle(list).overflowY === 'visible') list = list.parentElement;
  const view = list.getBoundingClientRect();
  const boxes = options.map((option) => option.getBoundingClientRect());
  const reached = options.find((option) => option.hasAttribute('data-highlighted'));
  const at = reached?.getBoundingClientRect();
  return {
    scrolls: list.scrollHeight - list.clientHeight > 1,
    gaps: boxes.slice(1).map((box, index) => Math.round((box.top - boxes[index].bottom) * 100) / 100),
    reachedInside: at ? at.top >= view.top - 0.5 && at.bottom <= view.bottom + 0.5 : null,
  };
}
"""


def read_menu(page: pw.Page) -> t.Dict[str, t.Any]:
    page_changes.wait_until_shown(page.get_by_role("option").first)
    return page.evaluate(MENU_JS)


def read_fit(page: pw.Page) -> t.Tuple[bool, t.List[float]]:
    """Whether the open menu scrolls, and its gaps of more than half a pixel."""
    menu: t.Dict[str, t.Any] = read_menu(page)
    return menu["scrolls"], [gap for gap in menu["gaps"] if abs(gap) > 0.5]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    labels: t.List[str] = [
        ins.call_api(
            check.instance,
            "POST",
            f"/projects/{project.id}/labels/",
            {"name": f"label {number:02}", "color": "#3b82f6"},
        )["id"]
        for number in range(30)
    ]
    ins.make_work_items(
        check.instance, project, [{"name": "one", "labels": labels[:1]}]
    )
    page: pw.Page = ll.open_list(check, account, project)
    line: pw.Locator = ll.line(page, "one")

    for height in (900, 500):
        page.set_viewport_size({"width": 1440, "height": height})
        for name in ("State", "Priority"):
            line.locator(f'button[aria-label^="{name}"]').click()
            check.expect(
                f"window {height} px high, the {name.lower()} of a line: all options show, without a scroll "
                "bar, one under the other",
                lambda: read_fit(page),
                (False, []),
            )
            page.keyboard.press("Escape")
            page_changes.wait_until_removed(page.get_by_role("option").first)

    page.set_viewport_size({"width": 1440, "height": 900})
    line.locator('button[aria-label^="Labels"]').click()
    check.expect(
        "thirty labels do not fit: that menu scrolls",
        lambda: read_menu(page)["scrolls"],
        True,
    )
    for _ in range(14):
        page.keyboard.press("ArrowDown")
        # a held key repeats some thirty times a second: keys sent faster than any hand leave the mark
        # outside what the menu shows
        page.wait_for_timeout(35)
    check.expect(
        "the option the arrow keys reach stays inside what the menu shows",
        lambda: read_menu(page)["reachedInside"],
        True,
    )
    page.context.close()
