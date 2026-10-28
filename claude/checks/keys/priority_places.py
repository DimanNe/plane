"""
P and the letter of a priority act on the work item that the keys act on wherever S and the letter of a state do:
the work item in the view beside the list, the page of one work item (where P opens the palette's page of
priorities), and the selected line of the timeline. A list that does not show priorities takes the letter after P
without a menu. In a list grouped by priority the selection stays at the place of the line that the letter sent to
another group, so that P M, P M works down a group. The list of shortcuts shows P and the letter of each priority.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import list_layout as ll
import page_changes
import steps

# The titles of the list of shortcuts that set a priority, each with the keys its badge shows.
SHORTCUTS_OF_PRIORITIES_JS: str = """
() => [...document.querySelectorAll('[role="dialog"][aria-labelledby] h4')]
  .filter((title) => title.textContent.startsWith('Set priority to'))
  .map((title) => [title.textContent, [...title.parentElement.querySelectorAll('kbd')].map((key) => key.textContent)])
"""


def read_priority(check: steps.Check, project: ins.Project, name: str) -> str:
    return ins.read_work_items(check.instance, project)[name]["priority"]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "in the view"},
            {"name": "on its page"},
            {
                "name": "on the timeline",
                "start_date": chart.day(0),
                "target_date": chart.day(1),
            },
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(page, "in the view")
    page.keyboard.press("Enter")
    page_changes.wait_until_shown(page.locator(ll.PANEL_TITLE))
    page.keyboard.press("p")
    check.expect(
        "the view beside the list open: P opens its menu of priorities",
        lambda: page.locator(ll.PROPERTY_MENU).count(),
        1,
    )
    page.keyboard.press("h")
    check.expect(
        "and H sets High",
        lambda: (
            read_priority(check, project, "in the view"),
            page.locator(ll.PROPERTY_MENU).count(),
        ),
        ("high", 0),
    )
    page.keyboard.press("Escape")
    page.keyboard.press("Control+/")
    page_changes.wait_until_shown(page.get_by_role("dialog", name="Keyboard shortcuts"))
    check.expect(
        "the list of shortcuts shows P and the letter of each priority",
        lambda: page.evaluate(SHORTCUTS_OF_PRIORITIES_JS),
        [
            ["Set priority to Urgent", ["P", "U"]],
            ["Set priority to High", ["P", "H"]],
            ["Set priority to Medium", ["P", "M"]],
            ["Set priority to Low", ["P", "L"]],
            ["Set priority to None", ["P", "N"]],
        ],
    )
    page.context.close()

    sequence: int = ins.call_api(
        check.instance,
        "GET",
        f"/projects/{project.id}/work-items/{ids['on its page']}/",
    )["sequence_id"]
    page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/browse/{project.identifier}-{sequence}/",
    )
    page_changes.wait_until_shown(page.get_by_text("on its page", exact=True).first)
    page.locator("body").click(position={"x": 5, "y": 300})
    page.keyboard.press("p")
    check.expect(
        "the page of a work item: P opens the palette's page of priorities",
        lambda: page.locator(ll.PALETTE).count(),
        1,
    )
    page.keyboard.press("l")
    check.expect(
        "and L sets Low and closes the palette",
        lambda: (
            read_priority(check, project, "on its page"),
            page.locator(ll.PALETTE).count(),
        ),
        ("low", 0),
    )
    page.context.close()

    page = chart.open_timeline(check, account, project)
    page.mouse.click(*chart.get_entry_point(page, "on the timeline"))
    page.mouse.move(*chart.find_empty_point(page))
    page.keyboard.press("p")
    check.expect(
        "the timeline, a line selected: P opens the menu of priorities at that line",
        lambda: (
            page.evaluate(
                ll.MENU_AT_CONTROL_JS,
                [
                    chart.line(page, "on the timeline").element_handle(),
                    ll.PROPERTY_MENU,
                    "priority",
                ],
            )
            or [None]
        )[:1],
        [True],
    )
    page.keyboard.press("u")
    check.expect(
        "and U sets Urgent",
        lambda: read_priority(check, project, "on the timeline"),
        "urgent",
    )
    page.context.close()

    grouped: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        grouped,
        [
            {"name": "one", "priority": "high"},
            {"name": "two", "priority": "high"},
            {"name": "three", "priority": "high"},
        ],
    )
    page = ll.open_list(check, account, grouped, group_by="priority")
    ll.select_line(page, "one")
    for moved, selected in (("one", "two"), ("two", "three")):
        page.keyboard.press("p")
        page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
        page.keyboard.press("m")
        check.expect(
            f"grouped by priority: P M sends {moved} to Medium, and the selection stays at its place, on {selected}",
            lambda: (read_priority(check, grouped, moved), ll.read_selected(page)),
            ("medium", [selected]),
        )
    page.context.close()

    hidden: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, hidden, [{"name": "priority not shown"}])
    path: str = (
        f"/workspaces/{check.instance.workspace}/projects/{hidden.id}/user-properties/"
    )
    kept: ins.JSONObject = ins.call_app(check.instance.url, account, "GET", path)
    ins.call_app(
        check.instance.url,
        account,
        "PATCH",
        path,
        {"display_properties": {**kept["display_properties"], "priority": False}},
    )
    page = ll.open_list(check, account, hidden, group_by=None)
    ll.select_line(page, "priority not shown")
    page.keyboard.press("p")
    page.keyboard.press("m")
    check.expect(
        "a list that does not show priorities: P M sets Medium without a menu",
        lambda: (
            read_priority(check, hidden, "priority not shown"),
            page.locator(ll.PROPERTY_MENU).count(),
            ll.line(page, "priority not shown")
            .locator('[data-filter-property="priority"]')
            .count(),
        ),
        ("medium", 0, 0),
    )
    page.context.close()
