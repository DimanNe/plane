"""
A group shows the parents of its work items. A parent that stands in another group of the list is drawn dimmed
above its sub-work items, and so is its own parent, up to one that the list does not show. Such a line only shows
the structure: a click opens its work item beside the list, the arrow keys pass over it, it cannot be dragged, and
nothing done in the group changes its work item.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "great", "state": "Done"},
            {"name": "grandparent", "state": "Backlog", "parent": "great"},
            {"name": "elsewhere", "state": "Todo"},
            {"name": "parent", "state": "Todo", "parent": "grandparent"},
            {"name": "child", "state": "Todo", "parent": "parent"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    check.expect(
        "each group shows the parents of its work items at every depth, those of another group dimmed",
        lambda: (ll.read_lines(page), ll.read_lines_in_another_group(page)),
        (
            [
                ["Backlog", 0, "great"],
                ["Backlog", 1, "grandparent"],
                ["Todo", 0, "elsewhere"],
                ["Todo", 0, "great"],
                ["Todo", 1, "grandparent"],
                ["Todo", 2, "parent"],
                ["Todo", 3, "child"],
                ["Done", 0, "great"],
            ],
            [["Backlog", "great"], ["Todo", "great"], ["Todo", "grandparent"]],
        ),
    )

    ll.select_line(page, "parent")
    page.keyboard.press("ArrowUp")
    check.expect(
        "the arrow keys pass over the dimmed lines",
        lambda: ll.read_selected(page),
        ["elsewhere"],
    )
    dimmed: pw.Locator = ll.line_in_group(page, "Todo", "grandparent")
    dimmed.click(position={"x": 6, "y": 10})
    check.expect(
        "a click on a dimmed line opens its work item beside the list and leaves the selection where it was",
        lambda: (ll.read_panel(page), ll.read_selected(page)),
        ("grandparent", ["elsewhere"]),
    )

    ll.carry(page, dimmed)
    ll.hold_over(page, ll.group_header(page, "In Progress"), down=0.5)
    browser.let_page_draw(page)
    check.expect(
        "a dimmed line is not dragged: nothing is drawn where it is carried",
        lambda: ll.read_drop_marks(page),
        [],
    )
    page.mouse.up()
    # the rule is that nothing is stored, so the step waits for what must not come
    check.expect_stays(
        "let go over another group, its work item keeps its state",
        lambda: ins.read_state_name(check.instance, project, "grandparent"),
        "Backlog",
        seconds=1,
    )
    page.context.close()
