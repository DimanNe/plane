"""
The header of every group of the list has a "+" right after its count. It opens the dialog of N I, with the caret in
its title, for a work item of what the group stands for: the group of the "+", whichever line is selected, and N I
afterwards takes the group of the selected line again. Ctrl+Enter stores the work item there with the description
given in the dialog, and its line is the selected one. In the list of a cycle or of a module the work item goes into
that cycle or module too, by the "+" and by N I.
"""

import re
import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

# The state and the priority that the dialog for a new work item begins with, as its buttons name them.
VALUES_OF_DIALOG_JS: str = """
(buttons) => buttons
  .map((button) => button.getAttribute('aria-label'))
  .filter((label) => label.startsWith('State, ') || label.startsWith('Priority, '))
"""


def read_dialog(page: pw.Page) -> t.List[t.Any]:
    """The state and the priority the open dialog gives the new work item, and whether the caret is in its title."""
    values: t.List[str] = (
        page.locator(ll.CREATE_DIALOG)
        .locator("button[aria-label]")
        .evaluate_all(VALUES_OF_DIALOG_JS)
    )
    return [*values, page.evaluate("() => document.activeElement?.name === 'name'")]


def close_dialog(page: pw.Page) -> None:
    page.keyboard.press("Escape")
    page.locator(ll.CREATE_DIALOG).wait_for(state="detached")


def read_stored(
    check: steps.Check, project: ins.Project, name: str
) -> t.Optional[t.List[t.Any]]:
    """The state, the priority and the description the server has stored for a work item; None while it is not
    stored."""
    states: t.Dict[str, str] = {
        state_id: state for state, state_id in project.states.items()
    }
    item: t.Optional[ins.JSONObject] = ins.read_work_items(check.instance, project).get(
        name
    )
    if item is None:
        return None
    description: str = re.sub("<[^>]+>", "", item["description_html"] or "")
    return [states[item["state"]], item["priority"], description]


def read_members(check: steps.Check, path: str) -> t.List[str]:
    """The names of the work items of a cycle or a module."""
    return sorted(
        item["name"] for item in ins.call_api(check.instance, "GET", path)["results"]
    )


def check_groups_of_state(
    check: steps.Check, project: ins.Project, page: pw.Page
) -> None:
    dialog: pw.Locator = page.locator(ll.CREATE_DIALOG)
    check.expect(
        'every group has the "+", also a group without work items',
        lambda: ll.read_groups(page),
        [
            ["Backlog", 1, 1, True],
            ["Todo", 1, 1, True],
            ["In Progress", 1, 1, True],
            ["Done", 0, 0, True],
            ["Cancelled", 0, 0, True],
        ],
    )

    ll.select_line(page, "in backlog")
    ll.plus_of_group(page, "Todo").click()
    check.expect(
        'the "+" of Todo opens the dialog of N I in Todo, although a line of Backlog is selected, with the caret in '
        "its title",
        lambda: read_dialog(page),
        ["State, Todo", "Priority, None", True],
    )
    page.keyboard.type("added to todo")
    dialog.locator(".ProseMirror").first.click()
    page.keyboard.type("with a description")
    page.keyboard.press("Control+Enter")
    check.expect(
        "Ctrl+Enter stores the work item in Todo, with its description",
        lambda: read_stored(check, project, "added to todo"),
        ["Todo", "none", "with a description"],
    )
    check.expect(
        "the dialog is closed, the group shows and counts the work item, and its line is the selected one and is "
        "tinted",
        lambda: (
            dialog.count(),
            ll.read_groups(page)[1],
            ll.read_selected(page),
            ll.read_tinted(page),
        ),
        (0, ["Todo", 2, 2, True], ["added to todo"], ["added to todo"]),
    )

    ll.select_line(page, "in backlog")
    ll.open_create_dialog(page)
    check.expect(
        'N I after the "+" takes the group of the selected line again',
        lambda: read_dialog(page),
        ["State, Backlog", "Priority, None", True],
    )
    close_dialog(page)

    ll.plus_of_group(page, "Done").click()
    page.wait_for_function("() => document.activeElement?.name === 'name'")
    page.keyboard.type("added to done")
    page.keyboard.press("Control+Enter")
    check.expect(
        "in a group without work items: stored in its state, and the group shows its one line",
        lambda: (
            read_stored(check, project, "added to done"),
            ll.read_groups(page)[3],
        ),
        (["Done", "none", ""], ["Done", 1, 1, True]),
    )

    ll.group_header(page, "In Progress").get_by_text("In Progress").click()
    check.expect(
        "a click on the name of a group folds it",
        lambda: ll.read_groups(page)[2],
        ["In Progress", 1, 0, True],
    )
    dialog.wait_for(state="detached")
    ll.plus_of_group(page, "In Progress").click()
    check.expect(
        'the "+" of a folded group unfolds it and opens the dialog in its state',
        lambda: (ll.read_groups(page)[2], read_dialog(page)),
        (["In Progress", 1, 1, True], ["State, In Progress", "Priority, None", True]),
    )
    close_dialog(page)
    ll.plus_of_group(page, "Backlog").focus()
    page.keyboard.press("Enter")
    check.expect(
        'Enter on the "+" that has the focus opens the dialog, and does not fold the group',
        lambda: (ll.read_groups(page)[0], read_dialog(page)),
        (["Backlog", 1, 1, True], ["State, Backlog", "Priority, None", True]),
    )
    close_dialog(page)


def check_list_of_cycle_or_module(
    check: steps.Check, page: pw.Page, where: str, members: str
) -> None:
    page.locator(ll.LINE).first.wait_for()
    ll.plus_of_group(page, "Todo").click()
    page.wait_for_function("() => document.activeElement?.name === 'name'")
    page.keyboard.type(f"by the + of {where}")
    page.keyboard.press("Control+Enter")
    ll.select_line(page, "in todo")
    ll.create_work_item(page, f"by N I in {where}")
    check.expect(
        f'the "+" and N I in the list of {where}: the work items are in {where}',
        lambda: read_members(check, members),
        sorted([f"by N I in {where}", f"by the + of {where}", "in todo"]),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project(
        {account: ins.ROLE_ADMIN}, cycle_view=True, module_view=True
    )
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "in backlog", "state": "Backlog"},
            {"name": "in todo", "state": "Todo"},
            {"name": "in progress", "state": "In Progress"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    check_groups_of_state(check, project, page)
    page.context.close()

    page = ll.open_list(check, account, project, group_by="priority")
    ll.plus_of_group(page, "High").click()
    check.expect(
        'grouped by priority: the "+" of High opens the dialog with that priority',
        lambda: read_dialog(page),
        ["State, Backlog", "Priority, High", True],
    )
    page.keyboard.type("added to high")
    page.keyboard.press("Control+Enter")
    check.expect(
        "and stores the work item with it",
        lambda: read_stored(check, project, "added to high"),
        ["Backlog", "high", ""],
    )
    page.context.close()

    page = ll.open_list(check, account, project, group_by=None)
    ll.plus_of_group(page, "All work items").click()
    check.expect(
        'a list that is not grouped: its one "+" opens the dialog in the state a project gives a new work item',
        lambda: read_dialog(page),
        ["State, Backlog", "Priority, None", True],
    )
    close_dialog(page)
    page.context.close()

    projects: str = f"/{check.instance.workspace}/projects/{project.id}"
    cycle: str = ins.call_api(
        check.instance, "POST", f"/projects/{project.id}/cycles/", {"name": "a cycle"}
    )["id"]
    module: str = ins.call_api(
        check.instance, "POST", f"/projects/{project.id}/modules/", {"name": "a module"}
    )["id"]
    for kind, place in (("cycle", cycle), ("module", module)):
        ins.call_api(
            check.instance,
            "POST",
            f"/projects/{project.id}/{kind}s/{place}/{kind}-issues/",
            {"issues": [ids["in todo"]]},
        )
        ins.set_display(
            check.instance,
            account,
            project,
            of_list=f"{kind}s/{place}/",
            layout="list",
            group_by="state",
            show_empty_groups=True,
        )
    page = browser.open_page(check, account, f"{projects}/cycles/{cycle}/")
    check_list_of_cycle_or_module(
        check, page, "the cycle", f"/projects/{project.id}/cycles/{cycle}/cycle-issues/"
    )
    page.goto(f"{check.instance.url}{projects}/modules/{module}/")
    check_list_of_cycle_or_module(
        check,
        page,
        "the module",
        f"/projects/{project.id}/modules/{module}/module-issues/",
    )
    page.context.close()
