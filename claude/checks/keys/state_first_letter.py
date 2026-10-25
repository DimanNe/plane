"""
S and the first letter of a state set that state, for every state of the project, its own states too: S B sets
Backlog. Where two states begin with the same letter, the letter means the first of them. The letters that were
there before keep their meaning: P still sets In Progress, and I does too. A letter that no state begins with is
typed into the menu that S opened, which stays open.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
import steps


def read_state_and_open_menus(
    check: steps.Check, project: ins.Project, page: pw.Page
) -> t.Tuple[str, int]:
    return (
        ins.read_state_name(check.instance, project, "set by letters"),
        page.locator(ll.PROPERTY_MENU).count(),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    project = ins.make_state(check.instance, project, "Blocked", "backlog")
    project = ins.make_state(check.instance, project, "Waiting", "started")
    project = ins.make_state(check.instance, project, "Review", "started")
    ins.make_work_items(
        check.instance, project, [{"name": "set by letters", "state": "Todo"}]
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(page, "set by letters")

    letter: str
    expected: str
    rule: str
    for letter, expected, rule in [
        (
            "b",
            "Backlog",
            "S B sets Backlog, the first of the states of B (Blocked is the other)",
        ),
        ("w", "Waiting", "S W sets Waiting, a state the project added"),
        ("i", "In Progress", "S I sets In Progress, the state of its first letter"),
        ("t", "Todo", "S T sets Todo"),
        ("p", "In Progress", "S P still sets In Progress"),
        ("r", "Review", "S R sets Review"),
        ("d", "Done", "S D sets Done"),
        ("c", "Cancelled", "S C sets Cancelled"),
    ]:
        page.keyboard.press("s")
        page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
        page.keyboard.press(letter)
        check.expect(
            f"{rule} (the stored state, menus open)",
            lambda: read_state_and_open_menus(check, project, page),
            (expected, 0),
        )

    page.keyboard.press("s")
    page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
    page.keyboard.press("x")
    check.expect_stays(
        "S X, which no state begins with, changes nothing, and the menu stays open (the stored state, menus open)",
        lambda: read_state_and_open_menus(check, project, page),
        ("Cancelled", 1),
    )
    page.keyboard.press("Escape")
    page.context.close()
