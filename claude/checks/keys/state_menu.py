"""
S on the selected line of the list opens the menu of states at that line, with the caret in its search. The letter
of a state as the next key (D, P, T or C) sets that state at once: the menu closes and leaves a picture of itself in
which that state is marked, and nothing is sent for a work item in that state already. Any other key makes the menu
an ordinary one. A letter whose state the project does not have says so, and the menu stays for a choice by hand. In
a title that is edited S is a letter, and a guest gets nothing from the keys.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import page_changes
import steps


def press_state_key(page: pw.Page, letter: str) -> None:
    page.evaluate(ll.WATCH_PICTURE_JS)
    page.keyboard.press("s")
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
    page.keyboard.press("s")
    check.expect(
        "S on the selected line opens the menu of states at that line's state, with the caret in its search",
        lambda: page.evaluate(
            ll.MENU_AT_CONTROL_JS,
            [ll.line(page, "second").element_handle(), ll.PROPERTY_MENU, "state_id"],
        ),
        [True, True, True],
    )
    page.evaluate(ll.WATCH_PICTURE_JS)
    page.keyboard.press("d")
    check.expect(
        "D: the state is Done at once, the menu has closed, and its picture marked Done",
        lambda: (
            ins.read_state_name(check.instance, project, "second"),
            page.locator(ll.PROPERTY_MENU).count(),
            page.evaluate("window.__marked"),
        ),
        ("Done", 0, "Done"),
    )
    letter: str
    state: str
    for letter, state in (("p", "In Progress"), ("t", "Todo"), ("c", "Cancelled")):
        press_state_key(page, letter)
        check.expect(
            f"{letter.upper()} after S sets {state}",
            lambda: (
                ins.read_state_name(check.instance, project, "second"),
                page.locator(ll.PROPERTY_MENU).count(),
            ),
            (state, 0),
        )
    writes.clear()
    press_state_key(page, "c")
    check.expect_stays(
        "S C on a work item that is Cancelled already closes the menu and sends nothing",
        lambda: (
            page.locator(ll.PROPERTY_MENU).count(),
            browser.read_writes(page, writes),
        ),
        (0, []),
    )

    page.keyboard.press("s")
    page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
    page.keyboard.press("ArrowDown")
    check.expect_stays(
        "S and Arrow Down: the menu stays open as an ordinary one",
        lambda: page.locator(ll.PROPERTY_MENU).count(),
        1,
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes it and sends nothing",
        lambda: (
            page.locator(ll.PROPERTY_MENU).count(),
            browser.read_writes(page, writes),
            ins.read_state_name(check.instance, project, "second"),
        ),
        (0, [], "Cancelled"),
    )
    page.keyboard.press("s")
    page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
    page.keyboard.press("r")
    check.expect(
        "S R in a project with no state Review: a message says so, and the menu stays open for a choice by hand",
        lambda: (
            any("Review" in text for text in ll.read_messages(page)),
            page.locator(ll.PROPERTY_MENU).count(),
        ),
        (True, 1),
    )
    page.locator(ll.PROPERTY_MENU).get_by_role("option").filter(
        has_text="Backlog"
    ).click()
    check.expect(
        "a choice by hand there is stored",
        lambda: ins.read_state_name(check.instance, project, "second"),
        "Backlog",
    )

    ll.line(page, "third").locator("p").first.click(position={"x": 8, "y": 8})
    title: pw.Locator = page.locator('input[aria-label="Work item title"]')
    page_changes.wait_until_shown(title)
    page.keyboard.press("End")
    page.keyboard.press("s")
    page.keyboard.press("d")
    check.expect_stays(
        "in a title that is edited S and D are letters of the title",
        lambda: (title.input_value(), page.locator(ll.PROPERTY_MENU).count()),
        ("thirdsd", 0),
    )
    page.keyboard.press("Escape")
    page.context.close()

    page = ll.open_list(check, guest, project, group_by=None)
    writes = browser.record_writes(page)
    ll.select_line(page, "first")
    page.keyboard.press("s")
    page.keyboard.press("d")
    check.expect_stays(
        "a guest: S opens no menu, and D sends nothing",
        lambda: (
            page.locator(ll.PROPERTY_MENU).count(),
            browser.read_writes(page, writes),
            ins.read_state_name(check.instance, project, "first"),
        ),
        (0, [], "Backlog"),
    )
    page.context.close()
