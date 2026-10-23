"""
The pointer that moves over a line of the list selects it, as the arrow keys do: the keys then act on that line
and go on from it. Only a move of the pointer selects: a line that comes under a still pointer, as the list
scrolls for a held key, does not. A menu open for the selected line keeps that line selected while the pointer
crosses others, and the view beside the list stays with the line it shows until a key or a click moves it. The
address follows a key or a click, not the pointer that only moves.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

STATE_AT_LINE: str = 'button[aria-label^="State, "]'


def hover(page: pw.Page, title: str) -> browser.Point:
    """The pointer onto a line, where it holds no control: in its left padding, before the id."""
    point: browser.Point = browser.get_point(ll.line(page, title), across=0.004)
    page.mouse.move(*point)
    browser.let_page_draw(page)
    return point


def read_line_at(page: pw.Page, point: browser.Point) -> t.Optional[str]:
    """The title of the line at a point of the page."""
    return page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y)?.closest('[id^=\"issue_\"]')?.querySelector('p')?.textContent",
        list(point),
    )


def read_address(page: pw.Page) -> str:
    return page.evaluate("location.pathname")


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    # made in this order, the work items are numbered from 1: line 0 is the project's first
    ins.make_work_items(
        check.instance,
        project,
        [{"name": f"line {number}", "state": "Backlog"} for number in range(40)],
    )
    page: pw.Page = ll.open_list(check, account, project)
    check.expect(
        "nothing is selected when the list opens",
        lambda: ll.read_selected(page),
        [],
    )
    address_of_list: str = read_address(page)
    home: str = f"/{check.instance.workspace}/{project.identifier.lower()}"

    hover(page, "line 3")
    check.expect(
        "the pointer moved onto a line selects it",
        lambda: ll.read_selected(page),
        ["line 3"],
    )
    hover(page, "line 5")
    check.expect(
        "and onto another line, that one",
        lambda: ll.read_selected(page),
        ["line 5"],
    )
    check.expect_stays(
        "the address stays as it was while the pointer only moves",
        lambda: read_address(page),
        address_of_list,
    )

    page.keyboard.press("ArrowDown")
    check.expect(
        "Arrow Down goes on from the line the pointer selected, and the address follows the key",
        lambda: (ll.read_selected(page), read_address(page)),
        (["line 6"], f"{home}-7/"),
    )

    hover(page, "line 8")
    page.keyboard.press("Enter")
    check.expect(
        "Enter opens the line the pointer selected beside the list, and the address follows it",
        lambda: (ll.read_selected(page), ll.read_panel(page), read_address(page)),
        (["line 8"], "line 8", f"{home}-9/"),
    )
    hover(page, "line 9")
    check.expect(
        "with the view open, the pointer selects another line, and the view stays with the line it shows",
        lambda: (ll.read_selected(page), ll.read_panel(page)),
        (["line 9"], "line 8"),
    )
    page.keyboard.press("ArrowDown")
    check.expect(
        "a key goes on from the line the pointer selected, and the view follows the key",
        lambda: (ll.read_selected(page), ll.read_panel(page)),
        (["line 10"], "line 10"),
    )
    page.keyboard.press("Escape")
    check.expect("Escape closes it", lambda: ll.read_panel(page), None)

    ll.select_line(page, "line 12")
    check.expect(
        "a click on the line the pointer selected makes the address follow it",
        lambda: (ll.read_selected(page), read_address(page)),
        (["line 12"], f"{home}-13/"),
    )

    pointer: browser.Point = hover(page, "line 2")
    for _ in range(25):
        page.keyboard.press("ArrowDown")
    check.expect(
        "Arrow Down, pressed again and again under a still pointer, scrolls the list along to the selected line",
        lambda: (ll.read_selected(page), read_line_at(page, pointer) != "line 2"),
        (["line 27"], True),
    )
    check.expect_stays(
        "a line that the list brings under the still pointer is not selected by it",
        lambda: ll.read_selected(page),
        ["line 27"],
    )

    ll.line(page, "line 27").locator(STATE_AT_LINE).click()
    page.locator(ll.PROPERTY_MENU).wait_for()
    hover(page, "line 25")
    hover(page, "line 24")
    check.expect_stays(
        "while the menu of the selected line is open, the pointer moved over other lines keeps it selected",
        lambda: (ll.read_selected(page), page.locator(ll.PROPERTY_MENU).count()),
        (["line 27"], 1),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes the menu, and the line stays selected",
        lambda: (page.locator(ll.PROPERTY_MENU).count(), ll.read_selected(page)),
        (0, ["line 27"]),
    )
