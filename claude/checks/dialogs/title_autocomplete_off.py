"""
The title of a new work item is new text each time: the browser offers no earlier entries in it and keeps nothing
typed there, in the dialog of N I and in the dialog of a work item for intake. Both titles are fields named "name",
and Chrome otherwise drops down over them what was typed into any field of that name, on any site.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import page_changes
import steps

# The autocomplete of the field that holds the title of the open dialog of a new work item.
TITLE_AUTOCOMPLETE_JS: str = """
() => [...document.querySelectorAll('[role="dialog"] input[name="name"]')].map((title) => title.autocomplete)
"""


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    # the API makes a project's intake when an update turns it on, not when the project is made with it on
    ins.call_api(
        check.instance, "PATCH", f"/projects/{project.id}/", {"intake_view": True}
    )
    ins.make_work_items(check.instance, project, [{"name": "a work item"}])
    page: pw.Page = ll.open_list(check, account, project)

    ll.open_create_dialog(page)
    check.expect(
        "the title of the dialog of N I has autocomplete off",
        lambda: page.evaluate(TITLE_AUTOCOMPLETE_JS),
        ["off"],
    )
    page.keyboard.press("Escape")
    page_changes.wait_until_removed(page.locator(ll.CREATE_DIALOG))

    intake: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/projects/{project.id}/intake/"
    )
    intake.get_by_role("button", name="Add work item").click()
    page_changes.wait_until_shown(intake.locator('[role="dialog"] input[name="name"]'))
    check.expect(
        "the title of the dialog of a work item for intake has autocomplete off",
        lambda: intake.evaluate(TITLE_AUTOCOMPLETE_JS),
        ["off"],
    )
