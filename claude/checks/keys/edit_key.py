"""
E on the selected line of the list opens the work item beside the list with the caret at the very beginning of its
description, and what is typed at once, before the editor is there, arrives in the description and reaches no
shortcut. With the view already open, E only puts the caret there. Escape and the close button give the keys back to
the list. E does nothing with no line selected, and is a letter in a title that is edited. A work item that loads
slowly still gets everything typed meanwhile; one that cannot be loaded says so, and Escape closes the view.
"""

import re
import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

CARET_IN_DESCRIPTION_JS: str = """
(id) => !!document.activeElement?.classList.contains('ProseMirror')
  && !!document.activeElement.closest(`#full-screen-portal [id="editor-container-${id}"]`)
"""


def read_description(check: steps.Check, project: ins.Project, name: str) -> str:
    html: str = (
        ins.read_work_items(check.instance, project)[name].get("description_html") or ""
    )
    return re.sub(r"<[^>]+>", "", html).replace("&nbsp;", " ")


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "first"},
            {"name": "with text", "description_html": "<p>existing text</p>"},
            {"name": "third"},
            {"name": "slow"},
            {"name": "unloadable"},
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
    page.wait_for_function(CARET_IN_DESCRIPTION_JS, arg=ids["first"])
    page.keyboard.type("typed after")
    check.expect(
        "E opens the selected line beside the list, and what was typed before the editor was there stands in the "
        "description before what was typed after",
        lambda: (ll.read_panel(page), read_description(check, project, "first")),
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
    page.keyboard.press("e")
    page.wait_for_function(CARET_IN_DESCRIPTION_JS, arg=ids["with text"])
    page.keyboard.type("word ")
    check.expect(
        "the caret stands at the very beginning of a description that has text",
        lambda: read_description(check, project, "with text"),
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
    page.wait_for_function(CARET_IN_DESCRIPTION_JS, arg=ids["third"])
    page.keyboard.type("in place")
    check.expect(
        "with the view already open for the line, E puts the caret in its description",
        lambda: read_description(check, project, "third"),
        "in place",
    )
    page.keyboard.press("Escape")
    page.locator(ll.PANEL_TITLE).wait_for(state="detached")

    # the answers with the work item are kept back until the step lets them through
    kept_back: t.List[pw.Route] = []
    work_item: t.Pattern[str] = re.compile(rf"/issues/{ids['slow']}/(\?.*)?$")
    page.route(
        work_item,
        lambda route: kept_back.append(route)
        if route.request.method == "GET"
        else route.continue_(),
    )
    ll.select_line(page, "slow")
    page.keyboard.press("e")
    page.keyboard.type("nc sd while it loads ", delay=40)
    check.expect(
        "while the work item loads, nothing has the caret, no dialog opens and the selection stays",
        lambda: (
            len(kept_back) > 0,
            page.evaluate("() => document.activeElement.isContentEditable"),
            page.locator(ll.CREATE_DIALOG).count(),
            ll.read_selected(page),
        ),
        (True, False, 0, ["slow"]),
    )
    route: pw.Route
    for route in kept_back:
        route.continue_()
    # Playwright hands a request to the check only while the check calls it, and the reads below go to the server;
    # so nothing of the work item is held any more
    page.unroute(work_item)
    page.wait_for_function(CARET_IN_DESCRIPTION_JS, arg=ids["slow"])
    page.keyboard.type("and after")
    check.expect(
        "when it has come, what was typed meanwhile is in its description, before what is typed after",
        lambda: read_description(check, project, "slow"),
        "nc sd while it loads and after",
    )
    page.keyboard.press("Escape")
    page.locator(ll.PANEL_TITLE).wait_for(state="detached")
    page.unroute_all()
    page.route(
        re.compile(rf"/issues/{ids['unloadable']}/(\?.*)?$"),
        lambda route: route.fulfill(status=404, json={"error": "not found"}),
    )
    ll.select_line(page, "unloadable")
    page.keyboard.press("e")
    check.expect(
        "a work item that cannot be loaded: the view says so",
        lambda: page.locator("#full-screen-portal").inner_text().split("\n")[0],
        "Work item does not exist",
    )
    page.keyboard.press("Escape")
    page.keyboard.press("ArrowUp")
    check.expect(
        "and Escape closes it, the keys being the list's again",
        lambda: ll.read_selected(page),
        ["slow"],
    )
    page.context.close()
