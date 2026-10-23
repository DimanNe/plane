"""
Ctrl+F is the browser's search of the page: the app takes nothing of it, neither its default nor the focus. The
command search of the top bar has one key, Alt+/, and the command palette shows that key beside it.
"""

import typing as t

import playwright.sync_api as pw

import list_layout as ll
import instance as ins
import steps

SEARCH: str = "input Search commands..."
# Whether some handler of the page took the default of the keys pressed, as seen after all of them: the listener is
# on the window, which a key reaches last.
RECORD_DEFAULT_PREVENTED_JS: str = """
() => {
  window.__defaultPreventedOfKeys = [];
  window.addEventListener('keydown', (e) => {
    if (e.key === 'f' || e.key === 'F') window.__defaultPreventedOfKeys.push(e.defaultPrevented);
  });
}
"""
# The text of the palette's command that focuses the command search, with its key.
COMMAND_OF_SEARCH_JS: str = """
() => [...document.querySelectorAll('[cmdk-item]')]
  .map((item) => item.innerText.replace(/\\s+/g, ' ').trim())
  .find((text) => text.startsWith('Focus search input')) ?? null
"""


def read_focus_and_default_prevented(page: pw.Page) -> t.Tuple[str, t.List[bool]]:
    return ll.read_focus(page), page.evaluate("() => window.__defaultPreventedOfKeys")


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "one"}])
    page: pw.Page = ll.open_list(check, account, project)
    page.evaluate(RECORD_DEFAULT_PREVENTED_JS)

    page.keyboard.press("Control+f")
    check.expect_stays(
        "Ctrl+F takes neither the default of the key nor the focus: the search of the page is the browser's (the "
        "focus, the default taken)",
        lambda: read_focus_and_default_prevented(page),
        ("page", [False]),
    )

    page.keyboard.press("Alt+/")
    check.expect(
        "Alt+/ puts the caret into the command search of the top bar",
        lambda: ll.read_focus(page),
        SEARCH,
    )
    page.keyboard.press("Escape")

    page.locator("body").click(position={"x": 5, "y": 300})
    page.keyboard.press("Control+k")
    page.keyboard.type("Focus search input")
    check.expect(
        "the command palette shows Alt+/ as the key of the command search, and no Ctrl+F",
        lambda: page.evaluate(COMMAND_OF_SEARCH_JS),
        "Focus search input Alt /",
    )
    page.context.close()
