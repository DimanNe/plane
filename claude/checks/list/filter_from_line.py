"""
A right click on a value of a line, such as its state or its priority, offers to filter the list by that
value: to show only it, or to add it to the filter in force. The filter that results is the list's own: it
shows above the list, is kept for the user on the server, and stays after a reload. A right click elsewhere
on the line opens the line's menu as it was.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# The entries of the open menu from top to bottom: "---" for a line between them, " (off)" after one that
# cannot be chosen.
MENU_JS: str = """
() => [...document.querySelectorAll('[role="menu"] [role="menuitem"], [role="menu"] [role="separator"]')]
  .map((entry) => entry.getAttribute('role') === 'separator'
    ? '---' : entry.textContent.trim() + (entry.getAttribute('aria-disabled') === 'true' ? ' (off)' : ''))
"""
# The conditions shown above the list, each with its parts joined by " | ".
CONDITIONS_JS: str = """
() => [...document.querySelectorAll('button[aria-label="Remove filter"]')]
  .filter((remove) => remove.getClientRects().length > 0)
  .map((remove) => remove.parentElement.innerText.replace(/\\s*\\n\\s*/g, ' | ').trim())
"""


def read_entries_above_usual_ones(page: pw.Page) -> t.List[str]:
    """The entries of the open menu that stand above its first dividing line; none when it has no such line."""
    entries: t.List[str] = page.evaluate(MENU_JS)
    return entries[: entries.index("---")] if "---" in entries else []


def open_menu_at(page: pw.Page, title: str, value: str) -> None:
    """A right click on a value of a line, found by the name its button has."""
    ll.line(page, title).get_by_role("button", name=value).first.click(button="right")
    page.get_by_role("menu").wait_for()


def read_stored_filter(
    check: steps.Check, account: ins.Account, project: ins.Project
) -> t.Any:
    path: str = (
        f"/workspaces/{check.instance.workspace}/projects/{project.id}/user-properties/"
    )
    return ins.call_app(check.instance.url, account, "GET", path)["rich_filters"]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "todo high", "state": "Todo", "priority": "high"},
            {"name": "todo low", "state": "Todo", "priority": "low"},
            {"name": "backlog high", "state": "Backlog", "priority": "high"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    todo: str = project.states["Todo"]

    open_menu_at(page, "todo high", "State")
    check.expect(
        "a right click on the state of a line: one menu, which begins with the two entries for that state",
        lambda: (
            page.get_by_role("menu").count(),
            read_entries_above_usual_ones(page),
        ),
        (1, ["Show only State: Todo", "Add State: Todo to the filter"]),
    )
    page.get_by_role("menuitem", name="Show only State: Todo").click()
    check.expect(
        '"Show only": the condition shows above the list, and the list shows the work items that meet it',
        lambda: (page.evaluate(CONDITIONS_JS), sorted(ll.read_titles(page))),
        (["State | is | Todo"], ["todo high", "todo low"]),
    )
    check.expect(
        "the filter is kept for the user on the server",
        lambda: read_stored_filter(check, account, project),
        {"state_id__in": todo},
    )

    open_menu_at(page, "todo high", "State")
    check.expect(
        'a value that is in the filter already: its "Add" entry is off',
        lambda: read_entries_above_usual_ones(page),
        ["Show only State: Todo", "Add State: Todo to the filter (off)"],
    )
    page.keyboard.press("Escape")
    check.expect(
        "one Escape closes the menu, and the right click opened nothing; the line is the selected one, as the "
        "pointer moved onto it",
        lambda: (
            page.get_by_role("menu").count(),
            ll.read_selected(page),
            ll.read_panel(page),
        ),
        (0, ["todo high"], None),
    )
    open_menu_at(page, "todo high", "Priority")
    page.get_by_role("menuitem", name="Add Priority: High to the filter").click()
    check.expect(
        '"Add" puts a second condition beside the first, and the list shows what meets both',
        lambda: (page.evaluate(CONDITIONS_JS), ll.read_titles(page)),
        (["State | is | Todo", "Priority | is | High"], ["todo high"]),
    )
    check.expect(
        "kept on the server",
        lambda: read_stored_filter(check, account, project),
        {"and": [{"state_id__in": todo}, {"priority__in": "high"}]},
    )
    page.reload()
    check.expect(
        "after a reload the filter is the same",
        lambda: (page.evaluate(CONDITIONS_JS), ll.read_titles(page)),
        (["State | is | Todo", "Priority | is | High"], ["todo high"]),
    )
    open_menu_at(page, "todo high", "Priority")
    page.get_by_role("menuitem", name="Show only Priority: High").click()
    check.expect(
        '"Show only" with two conditions in force: the filter is that one condition',
        lambda: (page.evaluate(CONDITIONS_JS), sorted(ll.read_titles(page))),
        (["Priority | is | High"], ["backlog high", "todo high"]),
    )
    page.get_by_role("button", name="Clear all").click()
    check.expect(
        '"Clear all" empties the filter, on the page and on the server',
        lambda: (
            page.evaluate(CONDITIONS_JS),
            sorted(ll.read_titles(page)),
            read_stored_filter(check, account, project),
        ),
        ([], ["backlog high", "todo high", "todo low"], {}),
    )

    ll.line(page, "todo low").locator("p").first.click(button="right")
    page.get_by_role("menu").wait_for()
    check.expect(
        "a right click on the title of a line: the menu of the line, without entries for a filter",
        lambda: (read_entries_above_usual_ones(page), page.evaluate(MENU_JS)[0]),
        ([], "Edit"),
    )
    page.keyboard.press("Escape")
    ll.line(page, "todo low").get_by_role("button", name="State").first.click()
    check.expect(
        "a left click on the state of a line opens the states to choose from, as before",
        lambda: page.get_by_role("option").filter(has_text="In Progress").count(),
        1,
    )
    page.context.close()
