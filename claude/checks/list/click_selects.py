"""
A click selects a line of the list, which is then drawn in a colour of its own. The pointer that moves over other
lines only highlights them, in another colour, and leaves the selection where it is: the arrow keys go on from the
selected line, and the keys of a line, E among them, act on it wherever the pointer is.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps


def move_pointer_onto(page: pw.Page, title: str) -> None:
    """The pointer moved as a hand moves it, across the lines on its way, onto a line where it holds no control:
    in its left padding, before the id."""
    page.mouse.move(*browser.get_point(ll.line(page, title), across=0.004), steps=12)
    browser.let_page_draw(page)


def read_colour(page: pw.Page, title: str) -> str:
    return ll.line(page, title).evaluate(
        "(line) => getComputedStyle(line).backgroundColor"
    )


def read_selected_and_colours(
    page: pw.Page, hovered: str, plain: str
) -> t.Tuple[t.List[str], bool, bool]:
    """The selected lines; whether the line under the pointer is drawn in a colour of its own, apart from a line
    that is neither selected nor under the pointer, and apart from the selected line."""
    selected: t.List[str] = ll.read_selected(page)
    hovered_colour: str = read_colour(page, hovered)
    return (
        selected,
        hovered_colour != read_colour(page, plain),
        bool(selected) and hovered_colour != read_colour(page, selected[0]),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [{"name": f"line {number}", "state": "Backlog"} for number in range(10)],
    )
    page: pw.Page = ll.open_list(check, account, project)

    ll.select_line(page, "line 2")
    check.expect(
        "a click selects a line",
        lambda: ll.read_selected(page),
        ["line 2"],
    )

    move_pointer_onto(page, "line 6")
    check.expect_stays(
        "the pointer moved over other lines leaves the selection where it is, and the line under it is highlighted, "
        "in a colour other than the selected line's (selected, highlighted, apart from the selected)",
        lambda: read_selected_and_colours(page, "line 6", plain="line 8"),
        (["line 2"], True, True),
    )

    page.keyboard.press("ArrowDown")
    check.expect(
        "Arrow Down selects the line after the selected one, not after the line under the pointer",
        lambda: ll.read_selected(page),
        ["line 3"],
    )

    move_pointer_onto(page, "line 5")
    page.keyboard.press("e")
    check.expect(
        "E, with the pointer on another line, puts the caret in the description of the selected line's work item, "
        "in the view beside the list (the view's title, the caret there, selected)",
        lambda: (
            ll.read_panel(page),
            page.evaluate(ll.CARET_IN_DESCRIPTION_JS, ids["line 3"]),
            ll.read_selected(page),
        ),
        ("line 3", True, ["line 3"]),
    )
    page.context.close()
