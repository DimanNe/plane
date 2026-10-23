"""
A session lasts while it is used. A person who signed in long ago and last used the app more than a week ago, as
before a holiday, is still signed in, and that visit renews the session to last as long as one just made: on the
server, and in the browser, which keeps the cookie of the session no longer than the server says.
"""

import datetime
import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import plane_config
import plane_runtime
import steps


def run_sql_on_session(instance: ins.Instance, session_key: str, sql: str) -> str:
    """Runs SQL in which :'session_key' names the session; through stdin, so that the key is in no command line."""
    return (
        plane_runtime.run_docker(
            [
                "exec",
                "-i",
                plane_runtime.get_container_name(
                    instance.run_dir, plane_config.Service.POSTGRES
                ),
                "psql",
                "-U",
                "plane",
                "-d",
                "plane",
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            capture=True,
            input=f"\\set session_key {session_key}\n{sql}\n".encode(),
        )
        .stdout.decode()
        .strip()
    )


def read_session_expiry(instance: ins.Instance, session_key: str) -> datetime.datetime:
    seconds: str = run_sql_on_session(
        instance,
        session_key,
        "select extract(epoch from expire_date) from sessions where session_key = :'session_key';",
    )
    return datetime.datetime.fromtimestamp(float(seconds), datetime.timezone.utc)


def move_session_back(instance: ins.Instance, session_key: str, days: int) -> None:
    """Makes the session look as if it was made, or last renewed, `days` earlier."""
    run_sql_on_session(
        instance,
        session_key,
        f"update sessions set expire_date = expire_date - interval '{days} days' "
        "where session_key = :'session_key';",
    )


def read_cookie_expiry(page: pw.Page, name: str) -> t.Optional[datetime.datetime]:
    """When the browser drops the cookie; None for one it drops with the browser's session."""
    cookie: pw.Cookie = next(
        cookie for cookie in page.context.cookies() if cookie["name"] == name
    )
    if cookie["expires"] < 0:
        return None
    return datetime.datetime.fromtimestamp(cookie["expires"], datetime.timezone.utc)


def round_to_minutes(difference: datetime.timedelta) -> int:
    return round(difference / datetime.timedelta(minutes=1))


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "first"}])
    # The first of the account's cookies is that of its session (see ACCOUNT_MAKER in instance.py).
    cookie_name: str
    session_key: str
    cookie_name, session_key = next(iter(account.cookies.items()))
    just_made: datetime.datetime = read_session_expiry(check.instance, session_key)
    move_session_back(check.instance, session_key, days=8)
    page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/projects/{project.id}/issues/"
    )
    check.expect(
        "a person who last used the app more than a week ago is still signed in: the page shows the project",
        lambda: (ll.read_titles(page), page.locator("input[name=email]").count()),
        (["first"], 0),
    )
    renewed: datetime.datetime = read_session_expiry(check.instance, session_key)
    check.expect(
        "the visit renewed the session on the server to last as long as one just made: by the minute, it ends "
        "when that one ends",
        lambda: round_to_minutes(renewed - just_made),
        0,
    )
    check.expect(
        "the browser keeps the cookie of the session as long as the server keeps the session, by the minute",
        lambda: round_to_minutes(read_cookie_expiry(page, cookie_name) - renewed),
        0,
    )
    page.context.close()
