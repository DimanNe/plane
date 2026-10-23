"""
A guest gets from Delete what the line's menu offers a guest: the menu offers no Delete, and the key neither asks
nor deletes.
"""

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    administrator: ins.Account = check.account()
    guest: ins.Account = check.account(ins.ROLE_GUEST)
    project: ins.Project = check.project(
        {administrator: ins.ROLE_ADMIN, guest: ins.ROLE_GUEST},
        guest_view_all_features=True,
    )
    ins.make_work_items(check.instance, project, [{"name": "of another"}])
    page: pw.Page = ll.open_list(check, guest, project)
    question: pw.Locator = page.locator(ll.QUESTION)
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
        lambda: (
            question.count(),
            ll.read_messages(page),
            ins.read_work_item_names(check.instance, project),
        ),
        (0, [], ["of another"]),
    )
    page.context.close()
