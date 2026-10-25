"""
Delete is the list's key only while nothing else takes keys: with no line selected, in a title that is edited and
with the dialog of a new work item open it deletes nothing and asks nothing, and Backspace on the selected line
does nothing.
"""

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
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
        lambda: (question.count(), ins.read_work_item_names(check.instance, project)),
        (0, ["kept", "other"]),
    )
    ll.select_line(page, "kept")
    page.keyboard.press("Backspace")
    check.expect_stays(
        "Backspace on the selected line does nothing",
        lambda: (
            question.count(),
            ll.read_selected(page),
            ins.read_work_item_names(check.instance, project),
        ),
        (0, ["kept"], ["kept", "other"]),
    )
    ll.line(page, "kept").locator("p").first.click(position={"x": 8, "y": 8})
    title: pw.Locator = page.locator('input[aria-label="Work item title"]')
    page_changes.wait_until_shown(title)
    page.keyboard.press("Home")
    page.keyboard.press("Delete")
    page.keyboard.press("Shift+Delete")
    check.expect_stays(
        "in a title that is edited Delete takes a letter and no work item",
        lambda: (
            title.input_value(),
            question.count(),
            ins.read_work_item_names(check.instance, project),
        ),
        ("ept", 0, ["kept", "other"]),
    )
    page.keyboard.press("Escape")
    page_changes.wait_until_removed(title)
    page.keyboard.press("n")
    page.keyboard.press("i")
    page_changes.wait_until_shown(page.locator(ll.CREATE_DIALOG))
    page.keyboard.press("Tab")
    page.keyboard.press("Delete")
    page.keyboard.press("Shift+Delete")
    check.expect_stays(
        "with the dialog of a new work item open the key does nothing",
        lambda: (question.count(), ins.read_work_item_names(check.instance, project)),
        (0, ["kept", "other"]),
    )
    page.context.close()
