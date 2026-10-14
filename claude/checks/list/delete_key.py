"""
Delete on the selected line of the list deletes as the line's menu does: it asks first, and Shift+Delete does
not. The selection goes to the line that took the place, and the work item view beside the list follows it. The
key is the list's only while nothing else takes keys, and a user gets from it what the menu offers that user.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def read_stored(check: steps.Check, project: ins.Project) -> t.List[str]:
    return sorted(ins.read_work_items(check.instance, project))


def check_key_of_an_administrator(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    names: t.List[str] = ["first", "second", "third", "fourth", "fifth", "sixth"]
    ins.make_work_items(check.instance, project, [{"name": name} for name in names])
    page: pw.Page = ll.open_list(check, account, project)
    question: pw.Locator = page.locator(ll.QUESTION)

    ll.select_line(page, "third")
    page.keyboard.press("Delete")
    check.expect(
        "Delete asks the question of the line's menu and deletes nothing yet",
        lambda: (question.count(), ll.read_selected(page), read_stored(check, project)),
        (1, ["third"], sorted(names)),
    )
    question.get_by_role("button", name="Cancel").click()
    check.expect(
        "Cancel leaves the work item, and its line selected",
        lambda: (question.count(), ll.read_selected(page), read_stored(check, project)),
        (0, ["third"], sorted(names)),
    )
    page.keyboard.press("Delete")
    question.get_by_role("button", name="Delete").click()
    # the question stays until the server has answered, and a key pressed meanwhile is lost (a fault of the page)
    check.expect(
        "confirmed, the question closes and the work item is gone from the list and from the server",
        lambda: (question.count(), ll.read_titles(page), read_stored(check, project)),
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
    # the rule is that the held key deletes nothing more, however long the page is given
    check.expect_stays(
        "and no second one after it",
        lambda: read_stored(check, project),
        ["first", "second"],
        seconds=1,
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
            read_stored(check, project),
        ),
        (["second"], "second", ["second"]),
    )
    page.context.close()


def check_key_that_is_not_the_lists(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "kept"}, {"name": "other"}])
    page: pw.Page = ll.open_list(check, account, project)
    question: pw.Locator = page.locator(ll.QUESTION)

    # In each of these the rule is that nothing is deleted and nothing asked, so each waits a moment for
    # what must not come.
    page.keyboard.press("Delete")
    page.keyboard.press("Shift+Delete")
    check.expect_stays(
        "with no line selected the key does nothing",
        lambda: (question.count(), read_stored(check, project)),
        (0, ["kept", "other"]),
        seconds=1,
    )
    ll.select_line(page, "kept")
    page.keyboard.press("Backspace")
    check.expect_stays(
        "Backspace on the selected line does nothing",
        lambda: (question.count(), ll.read_selected(page), read_stored(check, project)),
        (0, ["kept"], ["kept", "other"]),
        seconds=1,
    )
    ll.line(page, "kept").locator("p").first.click(position={"x": 8, "y": 8})
    title: pw.Locator = page.locator('input[aria-label="Work item title"]')
    title.wait_for()
    page.keyboard.press("Home")
    page.keyboard.press("Delete")
    page.keyboard.press("Shift+Delete")
    check.expect_stays(
        "in a title that is edited Delete takes a letter and no work item",
        lambda: (title.input_value(), question.count(), read_stored(check, project)),
        ("ept", 0, ["kept", "other"]),
        seconds=1,
    )
    page.keyboard.press("Escape")
    title.wait_for(state="detached")
    page.keyboard.press("n")
    page.keyboard.press("i")
    page.locator(ll.CREATE_DIALOG).wait_for()
    page.keyboard.press("Tab")
    page.keyboard.press("Delete")
    page.keyboard.press("Shift+Delete")
    check.expect_stays(
        "with the dialog of a new work item open the key does nothing",
        lambda: (question.count(), read_stored(check, project)),
        (0, ["kept", "other"]),
        seconds=1,
    )
    page.context.close()


def check_key_of_other_users(check: steps.Check, administrator: ins.Account) -> None:
    member: ins.Account = check.account(ins.ROLE_MEMBER)
    guest: ins.Account = check.account(ins.ROLE_GUEST)
    project: ins.Project = check.project(
        {
            administrator: ins.ROLE_ADMIN,
            member: ins.ROLE_MEMBER,
            guest: ins.ROLE_GUEST,
        },
        guest_view_all_features=True,
    )
    ins.make_work_items(check.instance, project, [{"name": "of another"}])
    ins.call_app(
        check.instance.url,
        member,
        "POST",
        f"/workspaces/{check.instance.workspace}/projects/{project.id}/issues/",
        {"name": "of the member", "state_id": project.states["Backlog"]},
    )
    page: pw.Page = ll.open_list(check, member, project)
    question: pw.Locator = page.locator(ll.QUESTION)

    ll.select_line(page, "of another")
    page.keyboard.press("Delete")
    question.get_by_role("button", name="Delete").click()
    check.expect(
        "a member who did not make the work item is refused by the question, as from the menu",
        lambda: any("permission" in text for text in ll.read_messages(page)),
        True,
    )
    refusal: t.List[str] = ll.read_messages(page)
    ll.close_message(page)
    ll.select_line(page, "of another")
    page.keyboard.press("Shift+Delete")
    check.expect(
        "and by Shift+Delete with the same message",
        lambda: ll.read_messages(page),
        refusal,
    )
    check.expect(
        "the work item stays, and stays selected",
        lambda: (read_stored(check, project), ll.read_selected(page)),
        (["of another", "of the member"], ["of another"]),
    )
    ll.select_line(page, "of the member")
    page.keyboard.press("Shift+Delete")
    check.expect(
        "a work item the member made is deleted",
        lambda: read_stored(check, project),
        ["of another"],
    )
    page.context.close()

    page = ll.open_list(check, guest, project)
    question = page.locator(ll.QUESTION)
    check.expect(
        "the menu of a line offers a guest no Delete",
        lambda: "Delete" in ll.read_menu_of_line(page, "of another"),
        False,
    )
    ll.select_line(page, "of another")
    page.keyboard.press("Delete")
    page.keyboard.press("Shift+Delete")
    # the rule is that nothing comes: no question, no message, no deletion
    check.expect_stays(
        "and the key neither asks a guest nor deletes",
        lambda: (question.count(), ll.read_messages(page), read_stored(check, project)),
        (0, [], ["of another"]),
        seconds=1,
    )
    page.context.close()


def check_key_on_a_sub_work_item(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "parent"},
            {"name": "child one", "parent": "parent"},
            {"name": "child two", "parent": "parent"},
            {"name": "after"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    ll.select_line(page, "child one")
    page.keyboard.press("Shift+Delete")
    check.expect(
        "a sub-work item is deleted alone, and the selection is on the line that took its place",
        lambda: (
            ll.read_lines(page),
            ll.read_selected(page),
            read_stored(check, project),
        ),
        (
            [
                ["Backlog", 0, "parent"],
                ["Backlog", 1, "child two"],
                ["Backlog", 0, "after"],
            ],
            ["child two"],
            ["after", "child two", "parent"],
        ),
    )
    page.context.close()


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    check_key_of_an_administrator(check, account)
    check_key_that_is_not_the_lists(check, account)
    check_key_of_other_users(check, account)
    check_key_on_a_sub_work_item(check, account)
