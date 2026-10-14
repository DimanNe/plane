"""
A work item made from the list is stored by Ctrl+Enter, which closes the dialog. The line of a new work item is
pointed out by a tint and is the selected one, so that the keys go on from it; a new sub-work item is pointed
out too, but its parent stays selected, so that the next one can follow.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def read_parent(check: steps.Check, project: ins.Project, name: str) -> t.Optional[str]:
    """The name of the parent the server has stored for a work item; None when it has none or is not stored."""
    items: t.Dict[str, ins.JSONObject] = ins.read_work_items(check.instance, project)
    names: t.Dict[str, str] = {item["id"]: title for title, item in items.items()}
    return names.get(items.get(name, {}).get("parent"))


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "one", "state": "Backlog"},
            {"name": "parent", "state": "Backlog"},
            {"name": "first child", "state": "Backlog", "parent": "parent"},
            {"name": "three", "state": "Backlog"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    dialog: pw.Locator = page.locator(ll.CREATE_DIALOG)

    check.expect(
        'the sidebar has no "New work item" button and the page no "Add work item" button: the keys, the '
        '"+" of a group and the command search are the ways',
        lambda: (
            page.get_by_role("complementary", name="Main sidebar")
            .get_by_role("button", name="New work item")
            .count(),
            page.get_by_role("button", name="Add work item").count(),
        ),
        (0, 0),
    )
    ll.select_line(page, "one")
    ll.create_work_item(page, "made new")
    check.expect(
        "N I, a title, Ctrl+Enter: the dialog is closed, and the new line is the selected one and is tinted",
        lambda: (dialog.count(), ll.read_selected(page), ll.read_tinted(page)),
        (0, ["made new"], ["made new"]),
    )
    check.expect(
        "the work item is stored, once",
        lambda: sorted(ins.read_work_items(check.instance, project)),
        ["first child", "made new", "one", "parent", "three"],
    )
    check.expect("the focus is on no control", lambda: ll.read_focus(page), "page")
    page.keyboard.press("ArrowUp")
    check.expect(
        "Arrow Up goes on from the new line",
        lambda: ll.read_selected(page),
        [ll.read_titles(page)[ll.read_titles(page).index("made new") - 1]],
    )

    ll.select_line(page, "parent")
    ll.create_work_item(page, "second child", keys="nc")
    check.expect(
        "N C makes a sub-work item of the selected line: its line is tinted, and the parent stays selected",
        lambda: (dialog.count(), ll.read_selected(page), ll.read_tinted(page)),
        (0, ["parent"], ["second child"]),
    )
    ll.create_work_item(page, "third child", keys="nc")
    check.expect(
        "N C once more, with no click between: the next sub-work item of the same parent",
        lambda: (
            read_parent(check, project, "second child"),
            read_parent(check, project, "third child"),
            ll.read_selected(page),
        ),
        ("parent", "parent", ["parent"]),
    )
    check.expect(
        "the list shows them under the parent",
        lambda: [line for line in ll.read_lines(page) if line[1] == 1],
        [
            ["Backlog", 1, "first child"],
            ["Backlog", 1, "second child"],
            ["Backlog", 1, "third child"],
        ],
    )

    ll.select_line(page, "one")
    ll.line(page, "three").hover()
    ll.line(page, "three").get_by_role("button", name="Add child").click()
    dialog.wait_for()
    page.keyboard.type("child by the line's button")
    page.keyboard.press("Control+Enter")
    check.expect(
        '"Add child" of a line that is not the selected one: Ctrl+Enter makes a sub-work item of that line and '
        "closes the dialog, and the selection stays",
        lambda: (
            read_parent(check, project, "child by the line's button"),
            dialog.count(),
            ll.read_selected(page),
        ),
        ("three", 0, ["one"]),
    )

    ll.open_create_dialog(page)
    dialog.get_by_role("switch", name="Create more").click()
    page.locator('input[name="name"]').click()
    page.keyboard.type("one of several")
    page.keyboard.press("Control+Enter")
    check.expect(
        'with "Create more" on, the dialog stays open and empty, and the new line is tinted behind it',
        lambda: (
            dialog.count(),
            page.locator('input[name="name"]').input_value(),
            ll.read_tinted(page),
        ),
        (1, "", ["one of several"]),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes a dialog in which nothing was typed, without a question",
        lambda: (dialog.count(), page.locator(ll.QUESTION).count()),
        (0, 0),
    )
    page.context.close()
