"""
A title typed on the page of a work item is stored while the page stays open: the server has it, and the title shows
it. The title also saves what is left unsaved when the page closes, and the check does not count on that.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import steps

TITLE: str = "#title-input"


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "quiet street"}])
    page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/browse/{project.identifier}-1/"
    )
    title: pw.Locator = page.locator(TITLE)
    check.expect(
        "the work item's page shows its title",
        lambda: title.input_value(),
        "quiet street",
    )
    title.click()
    page.keyboard.press("End")
    page.keyboard.type(" at night")
    check.expect(
        "what is typed into the title of the work item's page is stored, and the title shows it (server, title)",
        lambda: (
            ins.read_work_item_names(check.instance, project),
            title.input_value(),
        ),
        (["quiet street at night"], "quiet street at night"),
    )
    page.context.close()
