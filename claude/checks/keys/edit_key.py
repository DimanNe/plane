"""
E on the selected line of the list opens the work item beside the list with the caret at the very beginning of its
description, and what is typed at once, before the editor is there, arrives in the description and reaches no
shortcut. Escape gives the keys back to the list. E does nothing with no line selected.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "first"},
            {"name": "with text", "description_html": "<p>existing text</p>"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    page.keyboard.press("e")
    check.expect_stays(
        "with no line selected E opens nothing",
        lambda: ll.read_panel(page),
        None,
    )

    ll.select_line(page, "first")
    page.keyboard.press("e")
    page.keyboard.type("sd nc ", delay=35)
    page.wait_for_function(ll.CARET_IN_DESCRIPTION_JS, arg=ids["first"])
    page.keyboard.type("typed after")
    check.expect(
        "E opens the selected line beside the list, and what was typed before the editor was there stands in the "
        "description before what was typed after",
        lambda: (ll.read_panel(page), ll.read_description(check, project, "first")),
        ("first", "sd nc typed after"),
    )
    check.expect(
        "and reached no shortcut: the state is as it was, and no dialog opened",
        lambda: (
            ins.read_state_name(check.instance, project, "first"),
            page.locator(ll.CREATE_DIALOG).count(),
        ),
        ("Backlog", 0),
    )
    page.keyboard.press("Escape")
    page.locator(ll.PANEL_TITLE).wait_for(state="detached")
    page.keyboard.press("ArrowDown")
    check.expect(
        "Escape closes the view, and Arrow Down moves the selection again",
        lambda: (ll.read_selected(page), ll.read_panel(page)),
        (["with text"], None),
    )
    page.context.close()
