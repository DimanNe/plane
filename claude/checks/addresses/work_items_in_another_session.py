"""
In another session an address shows what it says: the address of the calendar opens the calendar, the address the
project had before turns into the new one with the layout used last, and the page of one work item keeps its
address. The address of a project that does not exist stays as typed and shows what the app shows for one, and a
word after the project that names no layout shows the app's page for what cannot be found.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import page_changes
import steps
import work_item_addresses as wa


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [{"name": f"item {number:02}", "state": "Backlog"} for number in range(1, 6)],
    )
    ins.set_display(
        check.instance,
        account,
        project,
        layout="list",
        group_by="state",
        order_by="sort_order",
    )
    workspace: str = f"/{check.instance.workspace}"
    home: str = f"{workspace}/{project.identifier.lower()}"

    other: pw.Page = browser.open_page(check, account, f"{home}/calendar/")
    check.expect(
        "in another session the address of the calendar opens the calendar",
        lambda: wa.read_page(other)[:2],
        (f"{home}/calendar/", "Calendar"),
    )
    other.goto(f"{check.instance.url}{workspace}/projects/{project.id}/issues")
    check.expect(
        "the address the project had before turns into the new one, with the layout used last",
        lambda: wa.read_page(other)[:2],
        (f"{home}/calendar/", "Calendar"),
    )
    other.goto(f"{check.instance.url}{workspace}/browse/{project.identifier}-3/")
    check.expect(
        "the page of one work item keeps its address",
        lambda: (
            other.evaluate("location.pathname"),
            other.get_by_text("item 03").count() > 0,
        ),
        (f"{workspace}/browse/{project.identifier}-3/", True),
    )

    other.goto(f"{check.instance.url}{workspace}/projects/{ins.NO_SUCH_ID}/issues/")
    # what the address shows once it has loaded: that the project does not exist
    page_changes.wait_until_shown(other.get_by_text("does not exist").first)
    no_project: str = wa.read_main_text(other)
    other.goto(f"{check.instance.url}{workspace}/nosuch/")
    check.expect(
        "the address of a project that does not exist stays as typed and shows what the app shows for one",
        lambda: (other.evaluate("location.pathname"), wa.read_main_text(other)),
        (f"{workspace}/nosuch/", no_project),
    )
    other.goto(f"{check.instance.url}{home}/nosuch/")
    check.expect(
        "an address with a word after the project that names no layout: the app's page for what cannot be found",
        lambda: "cannot be found" in other.locator("body").inner_text(),
        True,
    )
    other.context.close()
