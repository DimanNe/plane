"""
The short address of a project or a work item shows what its old address shows, whoever opens it: a guest
of the project gets its list, a member of the workspace who is not in a project gets the page of a project
that does not exist, and a number that no work item has gets the page of a work item that does not exist. A
project named as one of the app's own pages keeps its old address, and the word stays the page's.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps


def read_main_text(page: pw.Page) -> str:
    page.wait_for_load_state("networkidle")
    return page.locator("main").last.inner_text()


def run(check: steps.Check) -> None:
    administrator: ins.Account = check.account()
    guest: ins.Account = check.account(ins.ROLE_GUEST)
    member: ins.Account = check.account(ins.ROLE_MEMBER)
    project: ins.Project = check.project(
        {administrator: ins.ROLE_ADMIN, guest: ins.ROLE_GUEST},
        guest_view_all_features=True,
        network=0,
    )
    ins.make_work_items(check.instance, project, [{"name": "one"}, {"name": "two"}])
    workspace: str = f"/{check.instance.workspace}"
    home: str = f"{workspace}/{project.identifier.lower()}"

    page: pw.Page = browser.open_page(check, guest, f"{home}-2/")
    check.expect(
        "a guest of the project: the address of a work item opens the list with its line selected and its view open",
        lambda: (
            page.evaluate("location.pathname"),
            ll.read_selected(page),
            # a guest's view shows the title as text, so the view is known by the id in its header
            page.locator("#full-screen-portal")
            .get_by_text(f"{project.identifier}-2", exact=True)
            .count(),
        ),
        (f"{home}-2/", ["two"], 1),
    )
    page.context.close()

    page = browser.open_page(
        check, member, f"{workspace}/projects/{project.id}/issues/"
    )
    old: str = read_main_text(page)
    page.goto(f"{check.instance.url}{home}/")
    check.expect(
        "a member of the workspace who is not in the project: its short address shows what its old address "
        "shows, and stays as typed",
        lambda: (page.evaluate("location.pathname"), read_main_text(page)),
        (f"{home}/", old),
    )
    page.context.close()

    page = browser.open_page(
        check, administrator, f"{workspace}/browse/{project.identifier}-99999/"
    )
    # the page of one work item asks the server several times before it says that there is no such work item
    page.get_by_text("does not exist").first.wait_for(timeout=40_000)
    old = read_main_text(page)
    page.goto(f"{check.instance.url}{home}-99999/")
    check.expect(
        "a number that no work item has: the short address shows what the page of such a work item shows",
        lambda: read_main_text(page),
        old,
        timeout=40,
    )

    drafts: ins.Project = check.project(
        {administrator: ins.ROLE_ADMIN}, identifier="DRAFTS", name="Named as a page"
    )
    page.goto(f"{check.instance.url}{workspace}/projects/{drafts.id}/issues/")
    page.get_by_role("button", name="Display").wait_for()
    check.expect(
        "a project whose identifier is a word of the app's own pages keeps its old address",
        lambda: page.evaluate("location.pathname"),
        f"{workspace}/projects/{drafts.id}/issues/",
    )
    page.goto(f"{check.instance.url}{workspace}/drafts/")
    # The sidebar names every project of the workspace on every page, this one too, once it has loaded them; what
    # the address shows is the main part of the page, whose first line is its title.
    check.expect(
        "and that word is the app's page: here the workspace's Drafts",
        lambda: (
            page.evaluate("location.pathname"),
            page.locator("main").last.inner_text().split("\n")[0],
            page.locator("main").last.get_by_text("Named as a page").count(),
        ),
        (f"{workspace}/drafts/", "Drafts", 0),
    )
    page.context.close()
