"""
A person who opened the instance at another address than Plane's own, as through another interface of the host
or a tunnel, and signs in there stays at that address, signed in: what the server redirects to after signing in
does not lead to the origin Plane was configured with.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    # The checks reach the instance at localhost, which is Plane's own origin. 127.0.0.1 is the same instance at
    # another origin, where the browser holds no session: the one open_page gives is for localhost only.
    address: str = check.instance.url.replace("://localhost:", "://127.0.0.1:")
    page: pw.Page = browser.open_page(check, account, "/")
    page.goto(f"{address}/")
    page.locator("input[name=email]").click()
    page.keyboard.type(account.email)
    page.get_by_role("button", name="Continue").click()
    page.locator("input[name=password]").click()
    page.keyboard.type(account.password)
    page.get_by_role("button", name="Continue").click()
    check.expect(
        "after signing in at another address than Plane's own, the page is still at that address and the "
        "person is signed in there",
        lambda: (
            page.evaluate("location.origin"),
            page.evaluate(
                "fetch('/api/users/me/').then((response) => response.json()).then((me) => me.email)"
            ),
        ),
        (address, account.email),
    )
