"""
Display can hide the work items closed, completed or cancelled, for more than a number of days, 7 unless changed: the
list keeps every open work item and those closed lately, and the counts of its groups count only what it shows. The
wheel over the number changes it, a day a notch, up for more, without scrolling the dropdown, and so do the arrow
keys; the choice is kept, and shown again after a reload.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
import steps

OPEN: str = "Plan the release"
DONE_LATELY: str = "Write the changelog"
DONE_LONG_AGO: str = "Fix the login redirect"
CANCELLED_LATELY: str = "Translate the help pages"
CANCELLED_LONG_AGO: str = "Move the docs to the wiki"
ALL: t.List[str] = sorted(
    [OPEN, DONE_LATELY, DONE_LONG_AGO, CANCELLED_LATELY, CANCELLED_LONG_AGO]
)
# how long ago the work items closed long ago were closed, between two choices of the check
DAYS_AGO_CLOSED_LONG_AGO: float = 10

# A window too low for the whole of Display, whose panel then scrolls, and the wheel over the number could scroll it.
LOW_WINDOW: t.Dict[str, int] = {"width": 1440, "height": 560}
# the part of the panel that scrolls: how far it can, and how far it has
SCROLLED_JS: str = """
() => [...document.querySelectorAll('[data-filters-dropdown] *')]
  .filter((element) => element.scrollHeight > element.clientHeight + 1 && getComputedStyle(element).overflowY !== 'visible')
  .map((element) => [element.scrollHeight - element.clientHeight, element.scrollTop])
"""
SCROLL_TO_BOTTOM_JS: str = """
() => { for (const element of document.querySelectorAll('[data-filters-dropdown] *'))
  if (element.scrollHeight > element.clientHeight + 1 && getComputedStyle(element).overflowY !== 'visible')
    element.scrollTop = element.scrollHeight; }
"""


def read_shown(page: pw.Page) -> t.List[str]:
    return sorted(ll.read_titles(page))


def read_counts(page: pw.Page) -> t.Dict[str, int]:
    """The count beside each group's name, of the groups that hold closed work items."""
    return {
        name: count
        for name, count, _, _ in ll.read_groups(page)
        if name in ("Done", "Cancelled")
    }


def open_display(page: pw.Page) -> pw.Locator:
    page.get_by_role("button", name="Display").first.click()
    panel: pw.Locator = page.locator("[data-filters-dropdown]")
    page_changes.wait_until_shown(panel.get_by_role("spinbutton"))
    return panel


def read_days(panel: pw.Locator) -> t.List[t.Any]:
    """Whether hiding is on, and the days the number says."""
    number: pw.Locator = panel.get_by_role("spinbutton")
    return [number.get_attribute("aria-disabled") == "false", number.inner_text()]


def turn_wheel(page: pw.Page, panel: pw.Locator, notches: int) -> None:
    """Notches of a mouse wheel over the number, up for a positive count."""
    box: t.Optional[pw.FloatRect] = panel.get_by_role("spinbutton").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    for _ in range(abs(notches)):
        page.mouse.wheel(0, -100 if notches > 0 else 100)


# Notches of the wheel in one go, before the page can draw any of them, as a fast spin of a wheel sends them.
FAST_NOTCHES_JS: str = """
(count) => {
  const number = document.querySelector('[data-filters-dropdown] [role=spinbutton]');
  for (let notch = 0; notch < count; notch += 1)
    number.dispatchEvent(new WheelEvent('wheel', { deltaY: -100, bubbles: true, cancelable: true }));
}
"""


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": OPEN, "state": "Todo"},
            {"name": DONE_LATELY, "state": "Done"},
            {"name": DONE_LONG_AGO, "state": "Done"},
            {"name": CANCELLED_LATELY, "state": "Cancelled"},
            {"name": CANCELLED_LONG_AGO, "state": "Cancelled"},
        ],
    )
    ins.move_closing_back(
        check.instance,
        [ids[DONE_LONG_AGO], ids[CANCELLED_LONG_AGO]],
        DAYS_AGO_CLOSED_LONG_AGO,
    )
    page: pw.Page = ll.open_list(check, account, project)

    check.expect(
        "at first the list shows every work item, closed or not",
        lambda: read_shown(page),
        ALL,
    )
    panel: pw.Locator = open_display(page)
    check.expect(
        "Display offers to hide closed work items, off, at 7 days",
        lambda: read_days(panel),
        [False, "7 days"],
    )

    panel.get_by_role("button", name="Hide completed and cancelled").click()
    check.expect(
        "turned on, it hides the completed and the cancelled work items closed more than 7 days ago",
        lambda: read_shown(page),
        sorted([OPEN, DONE_LATELY, CANCELLED_LATELY]),
    )
    check.expect(
        "the groups count only the work items they show",
        lambda: read_counts(page),
        {"Done": 1, "Cancelled": 1},
    )

    window: t.Optional[t.Dict[str, int]] = page.viewport_size
    assert window is not None
    page.set_viewport_size(LOW_WINDOW)
    page_changes.wait_until_true(page, f"() => ({SCROLLED_JS})().length === 1")
    page.evaluate(SCROLL_TO_BOTTOM_JS)
    scrolled: t.List[t.List[int]] = page.evaluate(SCROLLED_JS)
    check.expect_at_least(
        "in a low window the panel of Display scrolls (pixels it can)",
        scrolled[0][0],
        1,
    )
    turn_wheel(page, panel, 5)
    check.expect(
        "five notches of the wheel up make it 12 days",
        lambda: read_days(panel),
        [True, "12 days"],
    )
    check.expect(
        "the wheel over the number does not scroll the panel",
        lambda: page.evaluate(SCROLLED_JS),
        scrolled,
    )
    page.set_viewport_size(window)
    page.evaluate(FAST_NOTCHES_JS, 3)
    check.expect(
        "three notches faster than the page draws them count as three: 15 days",
        lambda: read_days(panel),
        [True, "15 days"],
    )
    check.expect(
        "at 15 days the work items closed 10 days ago are shown again",
        lambda: read_shown(page),
        ALL,
    )

    turn_wheel(page, panel, -17)
    check.expect(
        "the wheel down goes to 0 days and no lower",
        lambda: read_days(panel),
        [True, "0 days"],
    )
    check.expect(
        "at 0 days every closed work item is hidden", lambda: read_shown(page), [OPEN]
    )
    check.expect(
        "the groups of closed work items count none",
        lambda: read_counts(page),
        {"Done": 0, "Cancelled": 0},
    )

    page.reload()
    page_changes.wait_until_shown(page.locator(ll.LINE).first)
    check.expect(
        "after a reload the list still hides every closed work item",
        lambda: read_shown(page),
        [OPEN],
    )
    panel = open_display(page)
    check.expect(
        "and Display still says 0 days", lambda: read_days(panel), [True, "0 days"]
    )

    panel.get_by_role("spinbutton").focus()
    for _ in range(7):
        page.keyboard.press("ArrowUp")
    check.expect(
        "seven presses of the up arrow make it 7 days",
        lambda: read_days(panel),
        [True, "7 days"],
    )
    check.expect(
        "and the work items closed lately are shown again",
        lambda: read_shown(page),
        sorted([OPEN, DONE_LATELY, CANCELLED_LATELY]),
    )

    panel.get_by_role("button", name="Hide completed and cancelled").click()
    check.expect(
        "turned off, the list shows every work item again",
        lambda: read_shown(page),
        ALL,
    )
    check.expect(
        "and the groups count them all",
        lambda: read_counts(page),
        {"Done": 2, "Cancelled": 2},
    )
    page.context.close()
