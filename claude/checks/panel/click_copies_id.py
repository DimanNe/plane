"""
A click on the id of a work item, in the header of the view beside the list, copies the id as plain text, and a
message says so; the view stays on that work item. This also works on a page that is not a secure context, where the
browser offers no Clipboard API (navigator.clipboard): a page opened over plain HTTP at an address that is not a
loopback one, as a browser on another machine of the network opens the instance by the name of the host.

The check opens the instance twice: at its own address, http://localhost:PORT, which is a secure context, and at
http://[::ffff:127.0.0.1]:PORT, the IPv4 loopback address written as an IPv6 one. That address reaches the port the
instance listens on, even when the instance is bound to 127.0.0.1 only, and a browser does not trust it over plain
HTTP: it trusts only localhost, 127.0.0.0/8 and ::1 ("Is origin potentially trustworthy?" in W3C Secure Contexts).
A step checks which of the two each page is, so that a browser that starts to trust that address fails the check
instead of no longer trying the copy without navigator.clipboard. The check reads the clipboard as a person does:
Ctrl+V into a text box.
"""

import typing as t
import urllib.parse

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

VIEW: str = "#full-screen-portal"
# Resolves to true once the condition put in place of %s holds of `arg`: at once, or at the change of the page that
# makes it hold; to false when no change has made it hold in the time given.
WAIT_FOR_PAGE_JS: str = """
([arg, timeoutMs]) => new Promise((resolve) => {
  const holds = %s;
  if (holds(arg)) {
    resolve(true);
    return;
  }
  let watch = null;
  const deadline = setTimeout(() => {
    watch.disconnect();
    resolve(false);
  }, timeoutMs);
  watch = new MutationObserver(() => {
    if (!holds(arg)) return;
    watch.disconnect();
    clearTimeout(deadline);
    resolve(true);
  });
  watch.observe(document, { childList: true, subtree: true, characterData: true, attributes: true });
})
"""
# Whether the view beside the list shows the work item of this title, with its id.
VIEW_SHOWS_JS: str = """
([panelTitle, view, title, id]) => document.querySelector(panelTitle)?.value === title
  && [...document.querySelectorAll(view + ' button')].some((button) => button.textContent === id)
"""
# Makes a text box, apart from the page's own elements, with the caret in it, and window.__pasted, which resolves to
# what the next paste into the box carries (its kinds of data, and its text), or to null when none comes in the time
# given.
PASTE_INTO_BOX_JS: str = """
(timeoutMs) => {
  const box = document.createElement('textarea');
  document.body.append(box);
  box.focus();
  window.__pasted = new Promise((resolve) => {
    const deadline = setTimeout(() => resolve(null), timeoutMs);
    box.addEventListener('paste', (event) => {
      clearTimeout(deadline);
      resolve([[...event.clipboardData.types], event.clipboardData.getData('text/plain')]);
    }, { once: true });
  });
}
"""


def wait_for_page_to_show(page: pw.Page, holds_js: str, arg: t.Any) -> None:
    """Returns as soon as the page shows what `holds_js` tells of `arg`, or after a step's time; the step after it
    says what the page showed."""
    page.evaluate(WAIT_FOR_PAGE_JS % holds_js, [arg, steps.STEP_TIMEOUT * 1000])


def read_clipboard(page: pw.Page) -> t.Optional[t.List[t.Any]]:
    """What the clipboard holds, as a person learns it, by Ctrl+V into a text box: its kinds of data, and its text."""
    page.evaluate(PASTE_INTO_BOX_JS, steps.STEP_TIMEOUT * 1000)
    page.keyboard.press("Control+V")
    return page.evaluate("window.__pasted")


def get_plain_http_origin(instance: ins.Instance) -> str:
    """The instance at the IPv4 loopback address written as an IPv6 one, which a browser does not trust (see above)."""
    return f"http://[::ffff:127.0.0.1]:{urllib.parse.urlsplit(instance.url).port}"


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance, project, [{"name": "first"}, {"name": "second"}]
    )

    # Each address opens another work item, so that a copy at the first address cannot pass for one at the second.
    origin: str
    where: str
    is_secure: bool
    title: str
    number: int
    for origin, where, is_secure, title, number in (
        (check.instance.url, "at the instance's own address", True, "first", 1),
        (
            get_plain_http_origin(check.instance),
            "at [::ffff:127.0.0.1]",
            False,
            "second",
            2,
        ),
    ):
        page: pw.Page = ll.open_list(check, account, project, origin=origin)
        check.expect(
            f"a page {where} is {'a' if is_secure else 'no'} secure context, "
            f"{'with' if is_secure else 'without'} navigator.clipboard",
            lambda: page.evaluate("[window.isSecureContext, 'clipboard' in navigator]"),
            [is_secure, is_secure],
            timeout=0,
        )
        if is_secure:
            # Chrome in a window lets the page that has the focus write to the clipboard, as it does for a person;
            # a headless one refuses navigator.clipboard.writeText unless told to allow it.
            page.context.grant_permissions(["clipboard-write"], origin=origin)
        id_of_work_item: str = f"{project.identifier}-{number}"
        ll.line(page, title).dblclick(position={"x": 6, "y": 10})
        shown: t.List[str] = [ll.PANEL_TITLE, VIEW, title, id_of_work_item]
        wait_for_page_to_show(page, VIEW_SHOWS_JS, shown)
        check.expect(
            f"a double click on a line opens its work item beside the list, with the id in the header ({where})",
            lambda: page.evaluate(VIEW_SHOWS_JS, shown),
            True,
            timeout=0,
        )

        page.locator(VIEW).get_by_text(id_of_work_item, exact=True).click()
        wait_for_page_to_show(
            page, "(message) => document.querySelector(message) !== null", ll.MESSAGE
        )
        check.expect(
            f"a click on the id in the view says that the id was copied ({where})",
            lambda: ll.read_messages(page),
            [f"ID copied! | {id_of_work_item} copied to clipboard"],
            timeout=0,
        )
        # FOR_REVIEWER: the waits of this check's own are driven by events. Two that it shares with every check look
        # on a schedule: expect_stays, which reads every 50 ms until settle.py (looking every 5 ms) says the page can
        # no longer change, and Playwright's own waits, in ll.open_list and click(). PLANE-88 left both to PLANE-87.
        check.expect_stays(
            f"the view stays on that work item ({where})",
            lambda: (ll.read_panel(page), page.evaluate(VIEW_SHOWS_JS, shown)),
            (title, True),
        )
        check.expect(
            f"the clipboard holds the id, as plain text only ({where})",
            lambda: read_clipboard(page),
            [["text/plain"], id_of_work_item],
            timeout=0,
        )
        page.context.close()
