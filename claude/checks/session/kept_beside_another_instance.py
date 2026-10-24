"""
Another Plane on the same host, as on another port, does not sign a person out of this one: neither a copy of this
instance imported from its export nor a Plane that names its cookies as Plane does unless told otherwise. A browser
keeps cookies by host name and sends each to every port of the host, so the instance keeps them under names of its
own. The cookies that the other sets when the person signs in there change nothing here: the person is still signed
in, what they change is stored, and the session of the admin pages is kept.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def read_cookie(page: pw.Page, name: str) -> t.Optional[str]:
    return next(
        (
            cookie["value"]
            for cookie in page.context.cookies()
            if cookie["name"] == name
        ),
        None,
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "first", "state": "Todo"}])
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    address: str = page.url
    # The second of the account's cookies is that of the session of the admin pages (see ACCOUNT_MAKER in instance.py).
    admin_cookie_name: str
    session_key: str
    admin_cookie_name, session_key = list(account.cookies.items())[1]
    page.context.add_cookies(
        [
            {"name": name, "value": ins.draw_name(128), "url": check.instance.url}
            for names in (
                ins.read_cookie_names_of_copy_on_another_port(check.instance),
                ins.DEFAULT_COOKIE_NAMES,
            )
            for name in names.values()
        ]
    )
    page.reload()
    check.expect(
        "after the other Plane on the same host set its cookies, the person is still signed in here",
        lambda: (
            page.url,
            ll.read_titles(page),
            page.locator("input[name=email]").count(),
        ),
        (address, ["first"], 0),
    )
    ll.select_line(page, "first")
    page.keyboard.press("s")
    page.locator(ll.PROPERTY_MENU).wait_for()
    page.keyboard.press("d")
    check.expect(
        "what the person changes here is stored: S D sets Done",
        lambda: ins.read_state_name(check.instance, project, "first"),
        "Done",
    )
    check.expect(
        "the session of the admin pages is kept",
        lambda: read_cookie(page, admin_cookie_name),
        session_key,
    )
    page.context.close()
