"""
P on the selected line of the list opens the menu of priorities at that line. The first letter of a priority as the
next key sets that priority at once: P U, P H, P M, P L and P N set Urgent, High, Medium, Low and None. The menu
closes and leaves a picture of itself in which that priority is marked, and nothing is sent for a work item that has
that priority already. Any other key leaves the menu open as an ordinary one. In a title that is edited P is a
letter, and a guest gets nothing from the keys.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import page_changes
import steps


def read_priority(check: steps.Check, project: ins.Project, name: str) -> str:
    return ins.read_work_items(check.instance, project)[name]["priority"]


def press_priority_key(page: pw.Page, letter: str) -> None:
    page.evaluate(ll.WATCH_PICTURE_JS)
    page.keyboard.press("p")
    page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
    page.keyboard.press(letter)


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    guest: ins.Account = check.account(ins.ROLE_GUEST)
    project: ins.Project = check.project(
        {account: ins.ROLE_ADMIN, guest: ins.ROLE_GUEST}, guest_view_all_features=True
    )
    ins.make_work_items(
        check.instance,
        project,
        [{"name": "first"}, {"name": "second"}, {"name": "third"}],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    writes: t.List[str] = browser.record_writes(page)

    ll.select_line(page, "second")
    page.keyboard.press("p")
    check.expect(
        "P on the selected line opens the menu of priorities at that line's priority",
        lambda: (
            page.evaluate(
                ll.MENU_AT_CONTROL_JS,
                [
                    ll.line(page, "second").element_handle(),
                    ll.PROPERTY_MENU,
                    "priority",
                ],
            )
            or [None, None]
        )[:2],
        [True, True],
    )
    page.evaluate(ll.WATCH_PICTURE_JS)
    page.keyboard.press("m")
    check.expect(
        "M: the priority is Medium at once, the menu has closed, and its picture marked Medium",
        lambda: (
            read_priority(check, project, "second"),
            page.locator(ll.PROPERTY_MENU).count(),
            page.evaluate("window.__marked"),
        ),
        ("medium", 0, "Medium"),
    )
    letter: str
    priority: str
    for letter, priority in (
        ("u", "urgent"),
        ("h", "high"),
        ("l", "low"),
        ("n", "none"),
    ):
        press_priority_key(page, letter)
        check.expect(
            f"P {letter.upper()} sets {priority.capitalize()}",
            lambda: (
                read_priority(check, project, "second"),
                page.locator(ll.PROPERTY_MENU).count(),
            ),
            (priority, 0),
        )
    writes.clear()
    press_priority_key(page, "n")
    check.expect_stays(
        "P N on a work item whose priority is None already closes the menu and sends nothing",
        lambda: (
            page.locator(ll.PROPERTY_MENU).count(),
            browser.read_writes(page, writes),
        ),
        (0, []),
    )

    page.keyboard.press("p")
    page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
    page.keyboard.press("ArrowDown")
    check.expect_stays(
        "P and Arrow Down: the menu stays open as an ordinary one",
        lambda: page.locator(ll.PROPERTY_MENU).count(),
        1,
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes it and sends nothing",
        lambda: (
            page.locator(ll.PROPERTY_MENU).count(),
            browser.read_writes(page, writes),
            read_priority(check, project, "second"),
        ),
        (0, [], "none"),
    )

    ll.line(page, "third").locator("p").first.click(position={"x": 8, "y": 8})
    title: pw.Locator = page.locator('input[aria-label="Work item title"]')
    page_changes.wait_until_shown(title)
    page.keyboard.press("End")
    page.keyboard.press("p")
    page.keyboard.press("m")
    check.expect_stays(
        "in a title that is edited P and M are letters of the title",
        lambda: (title.input_value(), page.locator(ll.PROPERTY_MENU).count()),
        ("thirdpm", 0),
    )
    page.keyboard.press("Escape")
    page.context.close()

    page = ll.open_list(check, guest, project, group_by=None)
    writes = browser.record_writes(page)
    ll.select_line(page, "first")
    page.keyboard.press("p")
    page.keyboard.press("m")
    check.expect_stays(
        "a guest: P opens no menu, and M sends nothing",
        lambda: (
            page.locator(ll.PROPERTY_MENU).count(),
            browser.read_writes(page, writes),
            read_priority(check, project, "first"),
        ),
        (0, [], "none"),
    )
    page.context.close()
