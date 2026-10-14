"""
The view of a work item beside the list: its header ends with an "x" that closes it, the id of the work item
stands once, in that header, and a click copies it; the title can be typed into and is stored. Closing the view leaves its line
selected.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

VIEW: str = "#full-screen-portal"
CLOSE: str = 'button[aria-label="Close the peek view"]'
# The places of the texts that show the id in the view: left, top, right, bottom of each.
PLACES_OF_ID_JS: str = """
([view, id]) => [...document.querySelectorAll(view + ' *')]
  .filter((element) => element.children.length === 0 && element.textContent.trim() === id
    && element.getClientRects().length > 0)
  .map((element) => { const r = element.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })
"""


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {
                "name": "with a description",
                "description_html": "<p>some words</p>",
            },
            {"name": "without one"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    view: pw.Locator = page.locator(VIEW)
    close: pw.Locator = view.locator(CLOSE)

    ll.select_line(page, "with a description")
    page.keyboard.press("Enter")
    close.wait_for()
    check.expect(
        'the right-most control of the view\'s header is the "x" that closes it',
        lambda: page.evaluate(
            """([view, close]) => {
              const header = document.querySelector(view + ' ' + close).parentElement.closest('div:has(a)');
              const controls = [...header.querySelectorAll('button, a')].filter((c) => c.getClientRects().length > 0);
              const last = controls.sort((a, b) => a.getBoundingClientRect().right - b.getBoundingClientRect().right).pop();
              return last.matches(close);
            }""",
            [VIEW, CLOSE],
        ),
        True,
    )
    id_of_work_item: str = f"{project.identifier}-1"
    places: t.List[t.List[float]] = page.evaluate(
        PLACES_OF_ID_JS, [VIEW, id_of_work_item]
    )
    bar: t.Optional[pw.FloatRect] = close.bounding_box()
    assert bar is not None
    check.expect(
        "the id of the work item stands once in the view, on the line of that button",
        lambda: [
            place[1] < bar["y"] + bar["height"] / 2 < place[3] for place in places
        ],
        [True],
        timeout=0,
    )

    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"], origin=check.instance.url
    )
    view.get_by_text(id_of_work_item, exact=True).click()
    check.expect(
        "a click on the id copies it",
        lambda: page.evaluate("navigator.clipboard.readText()"),
        id_of_work_item,
    )
    page.locator(ll.PANEL_TITLE).click()
    page.keyboard.press("End")
    page.keyboard.type(" renamed")
    check.expect(
        "what is typed into the title of the view is stored, and shows on the line",
        lambda: (
            sorted(ins.read_work_items(check.instance, project)),
            ll.read_titles(page)[0],
        ),
        (["with a description renamed", "without one"], "with a description renamed"),
    )
    close.click()
    check.expect(
        'a click on the "x" closes the view, and its line stays selected',
        lambda: (ll.read_panel(page), ll.read_selected(page)),
        (None, ["with a description renamed"]),
    )
    ll.line(page, "without one").dblclick(position={"x": 6, "y": 10})
    check.expect(
        "a double click on another line opens that work item",
        lambda: (ll.read_panel(page), ll.read_selected(page)),
        ("without one", ["without one"]),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes the view as the button does",
        lambda: (ll.read_panel(page), ll.read_selected(page)),
        (None, ["without one"]),
    )
    page.context.close()
