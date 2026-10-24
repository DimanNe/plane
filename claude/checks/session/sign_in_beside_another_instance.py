"""
A sign-in form of this instance still signs the person in after they signed in at another Plane on the same host
while it was open, a copy of this instance imported from its export too. The form holds Django's token against forged
requests from the moment it opened, and the server compares it with the cookie of that token. A browser sends a
host's cookies to every port of it, so the instance keeps the token in a cookie of its own name, which the other's
sign-in leaves alone.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    # The checks reach the instance at localhost, where the account is signed in. 127.0.0.1 is the same instance at
    # another origin, where the browser holds no session and the sign-in page is shown.
    address: str = check.instance.url.replace("://localhost:", "://127.0.0.1:")
    page: pw.Page = browser.open_page(check, account, "/")
    page.goto(f"{address}/")
    page.locator("input[name=email]").click()
    page.keyboard.type(account.email)
    with page.expect_response(lambda response: "/auth/get-csrf-token/" in response.url):
        page.get_by_role("button", name="Continue").click()
    # what the other Plane sets for this host when the person signs in there
    page.context.add_cookies(
        [
            {"name": name, "value": ins.draw_name(32), "url": address}
            for names in (
                ins.read_cookie_names_of_copy_on_another_port(check.instance),
                ins.DEFAULT_COOKIE_NAMES,
            )
            for name in names.values()
        ]
    )
    page.locator("input[name=password]").click()
    page.keyboard.type(account.password)
    page.get_by_role("button", name="Continue").click()
    check.expect(
        "the form that was open while the person signed in at the other Plane signs them in here",
        lambda: (
            page.evaluate("location.origin"),
            page.evaluate(
                "fetch('/api/users/me/').then((response) => response.json()).then((me) => me.email)"
            ),
        ),
        (address, account.email),
    )
    page.context.close()
