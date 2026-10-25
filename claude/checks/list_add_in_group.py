"""
What the checks of the "+" in the header of a group of the list need: list/add_in_group and the checks named after it.
"""

import re
import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
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
    page_changes.wait_until_removed(page.locator(ll.CREATE_DIALOG))


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


def check_list_of_cycle_or_module(
    check: steps.Check, page: pw.Page, where: str, members: str
) -> None:
    page_changes.wait_until_shown(page.locator(ll.LINE).first)
    ll.plus_of_group(page, "Todo").click()
    page_changes.wait_until_true(page, "() => document.activeElement?.name === 'name'")
    page.keyboard.type(f"by the + of {where}")
    page.keyboard.press("Control+Enter")
    ll.select_line(page, "in todo")
    ll.create_work_item(page, f"by N I in {where}")
    check.expect(
        f'the "+" and N I in the list of {where}: the work items are in {where}',
        lambda: read_members(check, members),
        sorted([f"by N I in {where}", f"by the + of {where}", "in todo"]),
    )
