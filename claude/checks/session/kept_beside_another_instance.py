"""
Another Plane on the same host, as on another port, does not sign a person out of this one. A browser keeps cookies
by host name and sends each to every port of the host, so the instance keeps its session in a cookie of its own
name: the cookie that another Plane sets under Plane's own name, after signing in there, changes nothing here.
"""

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# what Plane names its session cookie unless told otherwise (SESSION_COOKIE_NAME in apps/api/plane/settings)
PLANE_SESSION_COOKIE_NAME: str = "session-id"


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "first"}])
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    address: str = page.url
    page.context.add_cookies(
        [
            {
                "name": PLANE_SESSION_COOKIE_NAME,
                "value": ins.draw_name(128),
                "url": check.instance.url,
            }
        ]
    )
    page.reload()
    check.expect(
        "after another Plane on the same host set its session cookie, the person is still signed in here",
        lambda: (
            page.url,
            ll.read_titles(page),
            page.locator("input[name=email]").count(),
        ),
        (address, ["first"], 0),
    )
    page.context.close()
