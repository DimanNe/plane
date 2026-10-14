"""
N I with a line of a grouped list selected makes a new work item in that line's group: the dialog shows the group's
state, priority or label, and the work item is stored with it. In a list that is not grouped the dialog shows the
project's default state, as it always did, and a dialog in which nothing was typed closes on Escape without a
question.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# What the open dialog of a new work item shows as its state, priority and labels.
SHOWN_JS: str = """
() => {
  const dialog = [...document.querySelectorAll('[role="dialog"]')].find((d) => d.querySelector('input[name="name"]'));
  const said = (id) => dialog?.querySelector(`[data-testid="${id}"]`)?.innerText.trim() ?? null;
  return [said('create-work-item-state-select'), said('create-work-item-priority-select'), said('create-work-item-label-select')];
}
"""


def make_with_keys(
    check: steps.Check, project: ins.Project, page: pw.Page, title: str
) -> t.Tuple[t.List[t.Any], ins.JSONObject]:
    """N I, what the dialog shows, and the work item stored after its title is typed and Ctrl+Enter pressed: the
    dialog closes when the server has answered."""
    ll.open_create_dialog(page)
    shown: t.List[t.Any] = page.evaluate(SHOWN_JS)
    page.keyboard.type(title)
    page.keyboard.press("Control+Enter")
    page.locator(ll.CREATE_DIALOG).wait_for(state="detached")
    return shown, ins.read_work_items(check.instance, project)[title]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    label: ins.JSONObject = ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/labels/",
        {"name": "red", "color": "#cc3355"},
    )
    states: t.Dict[str, str] = {
        state_id: name for name, state_id in project.states.items()
    }
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "started", "state": "In Progress"},
            {"name": "high", "priority": "high"},
            {"name": "labelled", "labels": [label["id"]]},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by="state")
    ll.select_line(page, "started")
    shown, stored = make_with_keys(check, project, page, "new in a group of states")
    check.expect(
        "grouped by state: N I from a line in In Progress shows In Progress, and the work item is stored there",
        lambda: (shown[0], states[stored["state"]]),
        ("In Progress", "In Progress"),
    )
    page.keyboard.press("n")
    page.keyboard.press("i")
    page.locator(ll.CREATE_DIALOG).wait_for()
    page.keyboard.press("Escape")
    check.expect(
        "a dialog in which nothing was typed closes on Escape, without a question",
        lambda: (
            page.locator(ll.CREATE_DIALOG).count(),
            page.locator(ll.QUESTION).count(),
        ),
        (0, 0),
    )
    page.context.close()

    page = ll.open_list(check, account, project, group_by="priority")
    ll.select_line(page, "high")
    shown, stored = make_with_keys(check, project, page, "new in a group of priorities")
    check.expect(
        "grouped by priority: from a line of High, the dialog shows High, and the work item is stored so",
        lambda: (shown[1], stored["priority"]),
        ("High", "high"),
    )
    page.context.close()

    page = ll.open_list(check, account, project, group_by="labels")
    ll.select_line(page, "labelled")
    shown, stored = make_with_keys(check, project, page, "new in a group of labels")
    check.expect(
        "grouped by label: from a line of red, the dialog shows red, and the work item is stored with it",
        lambda: (shown[2], stored["labels"]),
        ("red", [label["id"]]),
    )
    page.context.close()

    page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(page, "started")
    shown, stored = make_with_keys(check, project, page, "new in a list not grouped")
    check.expect(
        "in a list that is not grouped, the dialog shows the project's default state and no priority",
        lambda: (shown[:2], states[stored["state"]], stored["priority"]),
        (["Backlog", "None"], "Backlog", "none"),
    )
    page.context.close()
