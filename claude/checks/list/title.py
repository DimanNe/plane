"""
A click on a line selects it and never opens it. A click on the title of a line edits the name in place:
Enter stores it, Escape puts the old name back, and a click on another line or an arrow key stores it and
goes on. A double click on a line opens its work item beside the list.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def read_names(check: steps.Check, project: ins.Project) -> t.List[str]:
    return sorted(ins.read_work_items(check.instance, project))


def edit_title(page: pw.Page, title: str) -> None:
    """A click on the title of a line; returns when the caret is in it."""
    ll.line(page, title).locator("p").first.click()
    page.wait_for_function("() => document.activeElement?.tagName === 'INPUT'")


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": name, "state": "Backlog"}
            for name in ("anna", "bob", "carla", "dora")
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)

    edit_title(page, "anna")
    check.expect(
        "a click on the title of a line: the line is selected, the title can be typed into, nothing is opened",
        lambda: (ll.read_selected(page), ll.read_focus(page)[:5], ll.read_panel(page)),
        (["anna"], "input", None),
    )
    page.keyboard.press("End")
    page.keyboard.type(" renamed")
    page.keyboard.press("Enter")
    check.expect(
        "Enter stores the name: the line shows it and stays selected, and the focus is on no control",
        lambda: (ll.read_titles(page)[0], ll.read_selected(page), ll.read_focus(page)),
        ("anna renamed", ["anna renamed"], "page"),
    )
    check.expect(
        "the server has the name",
        lambda: read_names(check, project),
        ["anna renamed", "bob", "carla", "dora"],
    )

    edit_title(page, "bob")
    page.keyboard.type("thrown away")
    page.keyboard.press("Escape")
    check.expect(
        "Escape while a title is edited puts the old name back, and the line stays selected",
        lambda: (ll.read_titles(page), ll.read_selected(page), ll.read_focus(page)),
        (["anna renamed", "bob", "carla", "dora"], ["bob"], "page"),
    )
    edit_title(page, "bob")
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    page.keyboard.press("Enter")
    check.expect(
        "a name that is empty is not stored: the old one is back",
        lambda: (ll.read_titles(page), read_names(check, project)),
        (
            ["anna renamed", "bob", "carla", "dora"],
            ["anna renamed", "bob", "carla", "dora"],
        ),
    )

    edit_title(page, "bob")
    page.keyboard.press("End")
    page.keyboard.type(" two")
    ll.select_line(page, "dora")
    check.expect(
        "a click on another line while a title is edited stores the name and selects that line",
        lambda: (read_names(check, project), ll.read_selected(page)),
        (["anna renamed", "bob two", "carla", "dora"], ["dora"]),
    )
    edit_title(page, "carla")
    page.keyboard.press("End")
    page.keyboard.type(" three")
    page.keyboard.press("ArrowDown")
    check.expect(
        "Arrow Down while a title is edited stores the name and selects the next line",
        lambda: (read_names(check, project), ll.read_selected(page)),
        (["anna renamed", "bob two", "carla three", "dora"], ["dora"]),
    )
    page.keyboard.press("ArrowUp")
    check.expect(
        "and the arrow keys go on moving the selection",
        lambda: ll.read_selected(page),
        ["carla three"],
    )

    ll.line(page, "dora").dblclick(position={"x": 6, "y": 10})
    check.expect(
        "a double click on a line opens its work item beside the list",
        lambda: (ll.read_selected(page), ll.read_panel(page)),
        (["dora"], "dora"),
    )
    page.context.close()
