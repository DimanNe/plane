"""
In a description that has text E puts the caret at its very beginning. After the close button of the view the keys
are the list's again, and in the view's title E is a letter. With the view already open for the line, E only puts
the caret in its description.
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
            {"name": "with text", "description_html": "<p>existing text</p>"},
            {"name": "third"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(page, "with text")
    page.keyboard.press("e")
    page.wait_for_function(ll.CARET_IN_DESCRIPTION_JS, arg=ids["with text"])
    page.keyboard.type("word ")
    check.expect(
        "the caret stands at the very beginning of a description that has text",
        lambda: ll.read_description(check, project, "with text"),
        "word existing text",
    )
    page.locator(
        '#full-screen-portal button[aria-label="Close the peek view"]'
    ).first.click()
    page.locator(ll.PANEL_TITLE).wait_for(state="detached")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    page.locator(ll.PANEL_TITLE).wait_for()
    page.locator(ll.PANEL_TITLE).click()
    page.keyboard.press("End")
    page.keyboard.press("e")
    check.expect(
        "after the close button the keys are the list's again; in the view's title E is a letter",
        lambda: page.locator(ll.PANEL_TITLE).input_value(),
        "thirde",
    )
    page.keyboard.press("Backspace")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.locator(ll.PANEL_TITLE).wait_for(state="detached")
    page.keyboard.press("Enter")
    page.locator(ll.PANEL_TITLE).wait_for()
    page.locator("body").click(position={"x": 5, "y": 400})
    ll.select_line(page, "third")
    page.keyboard.press("e")
    page.wait_for_function(ll.CARET_IN_DESCRIPTION_JS, arg=ids["third"])
    page.keyboard.type("in place")
    check.expect(
        "with the view already open for the line, E puts the caret in its description",
        lambda: ll.read_description(check, project, "third"),
        "in place",
    )
    page.keyboard.press("Escape")
    page.locator(ll.PANEL_TITLE).wait_for(state="detached")
    page.context.close()
