"""
Delete on the selected line of the list deletes as the line's menu does: it asks first, and Shift+Delete does
not. The selection goes to the line that took the place, and the work item view beside the list follows it.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    names: t.List[str] = ["first", "second", "third", "fourth", "fifth", "sixth"]
    ins.make_work_items(check.instance, project, [{"name": name} for name in names])
    page: pw.Page = ll.open_list(check, account, project)
    question: pw.Locator = page.locator(ll.QUESTION)

    ll.select_line(page, "third")
    page.keyboard.press("Delete")
    check.expect(
        "Delete asks the question of the line's menu and deletes nothing yet",
        lambda: (
            question.count(),
            ll.read_selected(page),
            ins.read_work_item_names(check.instance, project),
        ),
        (1, ["third"], sorted(names)),
    )
    question.get_by_role("button", name="Cancel").click()
    check.expect(
        "Cancel leaves the work item, and its line selected",
        lambda: (
            question.count(),
            ll.read_selected(page),
            ins.read_work_item_names(check.instance, project),
        ),
        (0, ["third"], sorted(names)),
    )
    page.keyboard.press("Delete")
    question.get_by_role("button", name="Delete").click()
    # the question stays until the server has answered, and a key pressed meanwhile is lost (a fault of the page)
    check.expect(
        "confirmed, the question closes and the work item is gone from the list and from the server",
        lambda: (
            question.count(),
            ll.read_titles(page),
            ins.read_work_item_names(check.instance, project),
        ),
        (
            0,
            ["first", "second", "fourth", "fifth", "sixth"],
            ["fifth", "first", "fourth", "second", "sixth"],
        ),
    )
    check.expect(
        "the selection is on the line that took the place",
        lambda: ll.read_selected(page),
        ["fourth"],
    )
    page.keyboard.press("ArrowDown")
    check.expect(
        "and Arrow Down goes on from there", lambda: ll.read_selected(page), ["fifth"]
    )

    page.keyboard.press("Shift+Delete")
    check.expect(
        "Shift+Delete deletes at once, and the selection is on the line that took the place",
        lambda: (ll.read_titles(page), ll.read_selected(page)),
        (["first", "second", "fourth", "sixth"], ["sixth"]),
    )
    check.expect(
        "with the message the menu's question gives, and no question",
        lambda: (
            any("deleted successfully" in text for text in ll.read_messages(page)),
            question.count(),
        ),
        (True, 0),
    )
    page.keyboard.press("Shift+Delete")
    check.expect(
        "after the last line the selection goes to the one before it",
        lambda: (ll.read_titles(page), ll.read_selected(page)),
        (["first", "second", "fourth"], ["fourth"]),
    )
    page.keyboard.down("Shift")
    _: int
    for _ in range(6):
        page.keyboard.down("Delete")
    page.keyboard.up("Delete")
    page.keyboard.up("Shift")
    check.expect(
        "a held Shift+Delete deletes one work item",
        lambda: (ll.read_titles(page), ll.read_selected(page)),
        (["first", "second"], ["second"]),
    )
    # the rule is that the held key deletes nothing more
    check.expect_stays(
        "and no second one after it",
        lambda: ins.read_work_item_names(check.instance, project),
        ["first", "second"],
    )

    ll.select_line(page, "first")
    page.keyboard.press("Enter")
    check.expect(
        "Enter opens the selected line beside the list",
        lambda: ll.read_panel(page),
        "first",
    )
    page.keyboard.press("Shift+Delete")
    check.expect(
        "deleted with the view open, the selection and the view are on the line that took the place",
        lambda: (
            ll.read_selected(page),
            ll.read_panel(page),
            ins.read_work_item_names(check.instance, project),
        ),
        (["second"], "second", ["second"]),
    )
    page.context.close()
