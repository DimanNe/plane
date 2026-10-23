"""
One line of the list is the selected one. A click selects it; the arrow keys move the selection through the
lines as they stand on the page, fold and unfold sub-work items, and Enter opens the selected line beside the
list, which then follows the selection. A selected work item that goes to another group by its own change stays
selected there; one that a state key sends away leaves the selection at its place.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def read_selection(page: pw.Page) -> t.Tuple[t.List[str], t.Optional[str]]:
    return ll.read_selected(page), ll.read_panel(page)


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "parent", "state": "Backlog"},
            {"name": "child one", "state": "Backlog", "parent": "parent"},
            {"name": "child two", "state": "Backlog", "parent": "parent"},
            {"name": "plain", "state": "Backlog"},
            {"name": "started", "state": "In Progress"},
            {"name": "started too", "state": "In Progress"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    check.expect(
        "the list shows the work items under their groups and parents",
        lambda: ll.read_lines(page),
        [
            ["Backlog", 0, "parent"],
            ["Backlog", 1, "child one"],
            ["Backlog", 1, "child two"],
            ["Backlog", 0, "plain"],
            ["In Progress", 0, "started"],
            ["In Progress", 0, "started too"],
        ],
    )
    check.expect(
        "nothing is selected when the list opens",
        lambda: read_selection(page),
        ([], None),
    )
    ll.select_line(page, "parent")
    check.expect(
        "a click on a line selects it and opens nothing",
        lambda: read_selection(page),
        (["parent"], None),
    )

    page.keyboard.press("ArrowDown")
    check.expect(
        "Arrow Down goes to the next line on the page, a sub-work item",
        lambda: read_selection(page),
        (["child one"], None),
    )
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    check.expect(
        "and on over the border of a group",
        lambda: read_selection(page),
        (["started"], None),
    )
    page.keyboard.press("ArrowUp")
    check.expect(
        "Arrow Up goes back over it", lambda: read_selection(page), (["plain"], None)
    )

    page.keyboard.press("Enter")
    check.expect(
        "Enter opens the selected line beside the list",
        lambda: read_selection(page),
        (["plain"], "plain"),
    )
    page.keyboard.press("ArrowUp")
    check.expect(
        "with the view open it follows the selection",
        lambda: read_selection(page),
        (["child two"], "child two"),
    )
    page.locator(ll.PANEL_TITLE).click()
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowDown")
    check.expect_stays(
        "arrow keys typed in the view's title are the title's",
        lambda: read_selection(page),
        (["child two"], "child two"),
    )
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes the view and keeps the selection",
        lambda: read_selection(page),
        (["child two"], None),
    )
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowUp")
    check.expect(
        "with the view closed the arrow keys open nothing",
        lambda: read_selection(page),
        (["parent"], None),
    )

    page.keyboard.press("ArrowLeft")
    check.expect(
        "Arrow Left folds the sub-work items of the selected line away",
        lambda: (ll.read_titles(page), ll.read_selected(page)),
        (["parent", "plain", "started", "started too"], ["parent"]),
    )
    page.keyboard.press("ArrowDown")
    check.expect(
        "Arrow Down passes over what is folded",
        lambda: ll.read_selected(page),
        ["plain"],
    )
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowRight")
    check.expect(
        "Arrow Right unfolds them again",
        lambda: ll.read_titles(page),
        ["parent", "child one", "child two", "plain", "started", "started too"],
    )

    ll.select_line(page, "plain")
    ins.call_api(
        check.instance,
        "PATCH",
        f"/projects/{project.id}/work-items/{ids['plain']}/",
        {"state": project.states["In Progress"]},
    )
    check.expect(
        "a selected work item that another session sends to another group stays selected there",
        lambda: (ll.read_lines(page)[3:], ll.read_selected(page)),
        (
            [
                ["In Progress", 0, "started"],
                ["In Progress", 0, "started too"],
                ["In Progress", 0, "plain"],
            ],
            ["plain"],
        ),
    )
    ll.select_line(page, "started")
    page.keyboard.press("s")
    page.keyboard.press("d")
    check.expect(
        "S and a state's letter send the selected line to that state, and the selection stays at its place",
        lambda: (ll.read_lines(page)[3:], ll.read_selected(page)),
        (
            [
                ["In Progress", 0, "started too"],
                ["In Progress", 0, "plain"],
                ["Done", 0, "started"],
            ],
            ["started too"],
        ),
    )
    check.expect(
        "and the state is stored",
        lambda: ins.read_work_items(check.instance, project)["started"]["state"],
        project.states["Done"],
    )
    page.context.close()
