"""
While the server does not answer, as when the instance's API is down and its proxy answers 502, a person who is
signed in is told neither to sign in nor that they are not a member of the workspace: the page says that Plane did
not answer, at the address it had, and shows what it showed by itself once the server answers again, without
signing in again.
"""

import re

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

CURRENT_USER: re.Pattern[str] = re.compile(r"/api/users/me/$")
MEMBERSHIP: re.Pattern[str] = re.compile(
    r"/api/workspaces/[^/]+/workspace-members/me/$"
)


def read_page(page: pw.Page) -> tuple:
    """The address, whether the page says that Plane did not answer, whether it says that the person is not a member
    of the workspace, and whether it asks for an email to sign in."""
    return (
        page.url,
        page.get_by_text("Looks like Plane didn't start up correctly!").is_visible(),
        page.get_by_text("Not Authorized!").is_visible(),
        page.locator("input[name=email]").count() > 0,
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "first"}])
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    address: str = page.url
    page.route(CURRENT_USER, lambda route: route.fulfill(status=502, body=""))
    page.reload()
    check.expect(
        "while the server does not say who is signed in, the page says that Plane did not answer, at its address, "
        "and asks nobody to sign in",
        lambda: read_page(page),
        (address, True, False, False),
    )
    page.unroute(CURRENT_USER)
    check.expect(
        "once the server answers again, the page shows what it showed, by itself and still signed in",
        lambda: (read_page(page), ll.read_titles(page)),
        ((address, False, False, False), ["first"]),
    )
    page.route(MEMBERSHIP, lambda route: route.fulfill(status=502, body=""))
    page.reload()
    check.expect(
        "while the server does not say whether the person is a member of the workspace, the page says that Plane "
        "did not answer, at its address, and not that they are not a member",
        lambda: read_page(page),
        (address, True, False, False),
    )
    page.unroute(MEMBERSHIP)
    check.expect(
        "once the server answers again, the page shows what it showed, by itself",
        lambda: (read_page(page), ll.read_titles(page)),
        ((address, False, False, False), ["first"]),
    )
    # the 502s were the check's own, not the server's
    check.server_errors[:] = [
        error
        for error in check.server_errors
        if not (
            error.startswith("502 GET ")
            and (CURRENT_USER.search(error) or MEMBERSHIP.search(error))
        )
    ]
    page.context.close()
