"""
From the letter after S on, the menu of states is only a picture: a click that comes at once, where the picture lies,
reaches the page under it. It selects the line there, and S and a letter then act on that line.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# Writes down whether the picture of the menu was on the page when the next press came.
WATCH_PRESS_JS: str = """
() => {
  window.__pictureAtPress = null;
  document.addEventListener('pointerdown', () => {
    window.__pictureAtPress = !!document.querySelector('.menu-choice-picture');
  }, { capture: true, once: true });
}
"""


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [{"name": "first"}, {"name": "second"}, {"name": "third"}, {"name": "fourth"}],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(page, "first")
    page.keyboard.press("s")
    menu: t.Optional[pw.FloatRect] = page.locator(ll.PROPERTY_MENU).bounding_box()
    under: t.Optional[pw.FloatRect] = ll.line(page, "third").bounding_box()
    assert menu is not None and under is not None
    # a point of the third line that the menu covers, past its title and the button beside it, which a click would
    # act on
    point: t.Tuple[float, float] = (
        menu["x"] + menu["width"] - 8,
        under["y"] + under["height"] / 2,
    )
    assert menu["y"] < point[1] < menu["y"] + menu["height"], (
        "the menu does not cover the third line"
    )
    page.evaluate(WATCH_PRESS_JS)
    page.keyboard.press("d")
    page.mouse.click(*point)
    check.expect(
        "a click at once after the letter, where the picture of the menu lies, selects the line under it, and the "
        "letter's state is stored",
        lambda: (
            page.evaluate("window.__pictureAtPress"),
            ll.read_selected(page),
            ins.read_state_name(check.instance, project, "first"),
        ),
        (True, ["third"], "Done"),
    )
    page.keyboard.press("s")
    page.locator(ll.PROPERTY_MENU).wait_for()
    page.keyboard.press("p")
    check.expect(
        "S P then acts on that line",
        lambda: ins.read_state_name(check.instance, project, "third"),
        "In Progress",
    )
    page.context.close()
