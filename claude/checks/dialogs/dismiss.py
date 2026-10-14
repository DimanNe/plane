"""
A pop-up closes on Escape and on a press outside it. A dialog with a form closes that way only while nothing
in it was changed: a field that was merely clicked into is not a change, typed text is. Escape on a dialog of
a new work item with a title asks before anything is lost.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps


def press_beside(page: pw.Page, pop_up: pw.Locator) -> None:
    """A press on the dimmed page, halfway between the left edge of the window and the pop-up."""
    box: pw.FloatRect = pop_up.bounding_box()
    page.mouse.click(box["x"] / 2, box["y"] + box["height"] / 2)


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "one"}])
    page: pw.Page = ll.open_list(check, account, project)
    dialog: pw.Locator = page.locator(ll.CREATE_DIALOG)
    search: pw.Locator = page.get_by_text("Workspace level", exact=True)

    page.get_by_placeholder("Search commands...").first.click()
    search.wait_for()
    # the search hangs from the top of the window; the lower part of the list is outside it
    page.mouse.click(
        *browser.get_point(page.locator(".vertical-scrollbar.scrollbar-lg"), down=0.9)
    )
    check.expect(
        "the command search closes on a press outside it", lambda: search.count(), 0
    )
    page.get_by_placeholder("Search commands...").first.click()
    search.wait_for()
    page.keyboard.press("Escape")
    check.expect("and on Escape", lambda: search.count(), 0)

    ll.select_line(page, "one")
    page.keyboard.press("Alt+/")
    check.expect(
        "Alt+/, also with a line selected, opens the command search of the top bar with the caret in it",
        lambda: (search.count() > 0, ll.read_focus(page)),
        (True, "input Search commands..."),
    )
    page.keyboard.press("Escape")
    check.expect(
        "and Escape closes it, leaving the line selected",
        lambda: (search.count(), ll.read_selected(page)),
        (0, ["one"]),
    )

    ll.open_create_dialog(page)
    page.keyboard.press("Escape")
    check.expect(
        "the dialog of a new work item, untouched, closes on Escape",
        lambda: dialog.count(),
        0,
    )
    ll.open_create_dialog(page)
    press_beside(page, dialog)
    check.expect(
        "and on a press on the dimmed page beside it", lambda: dialog.count(), 0
    )
    ll.open_create_dialog(page)
    dialog.locator(".ProseMirror").first.click()
    press_beside(page, dialog)
    check.expect(
        "a click into a field of it is no change: it still closes",
        lambda: dialog.count(),
        0,
    )

    ll.open_create_dialog(page)
    ll.choose_option(page, dialog.locator('button[aria-label^="State, "]'), "Todo")
    check.expect(
        "a choice in a drop-down of the dialog, which is drawn outside it, does not close the dialog",
        lambda: dialog.count(),
        1,
    )
    page.locator('input[name="name"]').click()
    page.keyboard.type("not saved yet")
    page.keyboard.press("Escape")
    question: pw.Locator = page.locator('[role="dialog"], [role="alertdialog"]').filter(
        has_text="Save this draft?"
    )
    check.expect(
        "with a title typed, Escape asks before it closes, and the form is still there behind the question",
        lambda: (question.count(), page.locator('input[name="name"]').input_value()),
        (1, "not saved yet"),
    )
    question.get_by_role("button", name="Discard").click()
    check.expect(
        "Discard in the question closes both",
        lambda: (question.count(), dialog.count()),
        (0, 0),
    )
    check.expect(
        "nothing was stored by all this",
        lambda: sorted(ins.read_work_items(check.instance, project)),
        ["one"],
    )
    page.context.close()
