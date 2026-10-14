"""
A long list draws only the lines near what the window shows; every other line has a stand-in. The stand-in
is as high as the line is when drawn, on every level, so the list is as long before a line is drawn as after
and the scroll bar does not jump. The title of a line is smaller on each level of sub-work items.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

LIST: str = ".vertical-scrollbar.scrollbar-lg"
# The place of a work item in the list: how high it is, and whether its line is drawn there.
PLACE_JS: str = """
(id) => {
  const place = document.querySelector(`[id^="issue_${id}_"]`);
  return [place.getBoundingClientRect().height, place.querySelector('[class~="group/list-block"]') !== null];
}
"""


def make_family(where: str) -> t.List[ins.JSONObject]:
    """A work item with a sub-work item that has one of its own: a line of each level."""
    return [
        {"name": f"{where} parent"},
        {"name": f"{where} child", "parent": f"{where} parent"},
        {"name": f"{where} grandchild", "parent": f"{where} child"},
    ]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        make_family("first")
        + [{"name": f"between {number:02}"} for number in range(60)]
        + make_family("last"),
    )
    kinds: t.List[str] = [
        f"{where} {level}"
        for where in ("first", "last")
        for level in ("parent", "child", "grandchild")
    ]
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    list_view: pw.Locator = page.locator(LIST)

    def read_places() -> t.Dict[str, t.List[t.Any]]:
        return {kind: page.evaluate(PLACE_JS, ids[kind]) for kind in kinds}

    check.expect(
        "at the top of a long list the first lines are drawn and the last ones are not",
        lambda: [drawn for _, drawn in read_places().values()],
        [True, True, True, False, False, False],
    )
    at_top: t.Dict[str, t.List[t.Any]] = read_places()
    check.expect(
        "the title of a line is 14 px, and 13 and 12 px on the levels under it",
        lambda: [
            ll.line(page, f"first {level}")
            .locator("p")
            .first.evaluate("(title) => getComputedStyle(title).fontSize")
            for level in ("parent", "child", "grandchild")
        ],
        ["14px", "13px", "12px"],
    )
    lengths: t.List[int] = [list_view.evaluate("(list) => list.scrollHeight")]
    page.mouse.move(*browser.get_point(list_view))
    for _ in range(12):
        page.mouse.wheel(0, 400)
        browser.let_page_draw(page)
        lengths.append(list_view.evaluate("(list) => list.scrollHeight"))
    check.expect(
        "the list is as long at every stop of the wheel on the way down (lengths seen)",
        lambda: sorted(set(lengths)),
        lengths[:1],
        timeout=0,
    )
    check.expect(
        "at the end the last lines are drawn and the first ones are not",
        lambda: [drawn for _, drawn in read_places().values()],
        [False, False, False, True, True, True],
    )
    at_end: t.Dict[str, t.List[t.Any]] = read_places()
    check.expect(
        "on every level a line stands in at the height it has when drawn (stand-in, drawn)",
        lambda: {
            kind: sorted([at_top[kind][0], at_end[kind][0]])
            for kind in kinds
            if at_top[kind][0] != at_end[kind][0]
        },
        {},
        timeout=0,
    )
    page.context.close()
