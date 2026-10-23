"""
A click on an arrow selects it and opens its control at the arrow: linked, "in ≥ n d", "on" a day, and the removal,
with the choice that holds marked. What is chosen there, typed into its number or turned by the wheel over its
number or its day, is shown at once and stored when the control closes by Enter or by a click elsewhere; Escape
drops it. The removal, and Delete on the selected arrow, remove it; Delete and Backspace typed in the number do not,
and nor does Backspace on the selected arrow.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps


def read_stored_arrows(check: steps.Check, project: ins.Project) -> t.List[chart.Arrow]:
    return chart.read_stored(check.instance, project)[1]


def turn_wheel_over(page: pw.Page, item: pw.Locator, notches: int) -> None:
    """The wheel over an item of the control, near its right edge, where no field takes the focus."""
    box: t.Optional[pw.FloatRect] = item.bounding_box()
    assert box is not None
    chart.turn_wheel(
        page, (box["x"] + box["width"] - 6, box["y"] + box["height"] / 2), notches
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(1), "target_date": chart.day(2)},
            {
                "name": "second",
                "start_date": chart.day(5),
                "target_date": chart.day(7),
                "is_start_fixed": False,
            },
            {
                "name": "third",
                "start_date": chart.day(10),
                "target_date": chart.day(10),
            },
            {
                "name": "fourth",
                "start_date": chart.day(6),
                "target_date": chart.day(7),
                "is_start_fixed": False,
            },
        ],
        [
            ("first", "second", "end-start", 2),
            ("second", "third", "end-start", 0),
            ("second", "fourth", "end-end", 0),
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=3)
    writes: t.List[str] = browser.record_writes(page)
    px_per_day: float = chart.get_px_per_day(page)
    page.mouse.click(*chart.get_bar_point(page, "first"))
    chart.hover_arrow(page, "first", "second")
    check.expect(
        "the pointer on an arrow: its line and its text say that it is under the pointer",
        lambda: (
            chart.read_arrow_looks(page)[("first", "second")][1],
            chart.read_text_looks(page)[("first", "second")][1],
        ),
        ("hovered", "hovered"),
    )

    control: pw.Locator = chart.open_arrow_control(page, "first", "second")
    check.expect(
        "a click on an arrow opens its control, with in ≥ n d marked as the choice that holds, and its days",
        lambda: chart.read_control(page),
        [["in ≥ d"], "2"],
    )
    check.expect(
        "the arrow is selected, drawn in the accent colour, and no task is selected any more",
        lambda: (
            chart.read_arrow_looks(page)[("first", "second")],
            chart.read_selected(page),
        ),
        (("accent", "selected"), []),
    )
    control.get_by_role("button", name="linked").click()
    check.expect(
        "linked chosen: the next task touches the first at once, and nothing is sent while the control is open",
        lambda: (
            chart.read_control(page),
            chart.read_bars(page)["second"],
            browser.read_writes(page, writes),
        ),
        ([["linked"], "0"], (chart.day(3), chart.day(5), False), []),
    )
    chart.click_away(page)
    check.expect(
        "a click elsewhere closes the control and stores the choice, in one request",
        lambda: (
            chart.read_control(page),
            read_stored_arrows(check, project)[0],
            chart.read_texts(page).get(("first", "second")),
            len(browser.read_writes(page, writes)),
        ),
        (None, ("first", "second", "end-start", None), "linked", 1),
    )

    control = chart.open_arrow_control(page, "first", "second")
    control.get_by_label("Delay in days").fill("4")
    check.expect(
        "4 typed into the number: in ≥ n d is the choice, the next task stands four days later, and the text "
        "over the arrow counts with it",
        lambda: (
            chart.read_control(page),
            chart.read_bars(page)["second"],
            chart.read_texts(page).get(("first", "second")),
        ),
        ([["in ≥ d"], "4"], (chart.day(7), chart.day(9), False), "in ≥ 4 d"),
    )
    page.keyboard.press("Enter")
    check.expect(
        "Enter closes the control and stores the days",
        lambda: (chart.read_control(page), read_stored_arrows(check, project)[0]),
        (None, ("first", "second", "end-start", 4)),
    )
    stored: t.Tuple[t.Dict[str, chart.Task], t.List[chart.Arrow]] = chart.read_stored(
        check.instance, project
    )
    writes.clear()
    control = chart.open_arrow_control(page, "first", "second")
    control.get_by_label("Delay in days").fill("6")
    page.keyboard.press("Escape")
    check.expect_stays(
        "Escape closes the control, puts the arrow back and stores nothing",
        lambda: (
            chart.read_control(page),
            chart.read_bars(page)["second"],
            chart.read_stored(check.instance, project),
            browser.read_writes(page, writes),
        ),
        (None, (chart.day(7), chart.day(9), False), stored, []),
    )

    control = chart.open_arrow_control(page, "first", "second")
    check.expect(
        "the control is open and its number does not have the focus",
        lambda: page.evaluate("document.activeElement.tagName"),
        "DIV",
    )
    turn_wheel_over(page, control.get_by_label("Delay in days").locator(".."), 3)
    check.expect(
        "three notches of the wheel over the number: three days more, shown at once, and the chart is not zoomed",
        lambda: (
            chart.read_control(page),
            chart.read_bars(page)["second"],
            chart.get_px_per_day(page),
        ),
        ([["in ≥ d"], "7"], (chart.day(10), chart.day(12), False), px_per_day),
    )
    chart.click_away(page)
    check.expect(
        "a click elsewhere stores them",
        lambda: read_stored_arrows(check, project)[0],
        ("first", "second", "end-start", 7),
    )

    control = chart.open_arrow_control(page, "second", "third")
    check.expect(
        "the control of an arrow into a fixed task has on and its day marked",
        lambda: chart.read_control(page)[0],
        [f"on {chart.format_day(chart.day(10))}"],
    )
    turn_wheel_over(
        page, control.get_by_role("button", name="on", exact=True).locator(".."), 2
    )
    check.expect(
        "two notches over the day: the next task is fixed two days later",
        lambda: chart.read_bars(page)["third"],
        (chart.day(12), chart.day(12), True),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape puts it back",
        lambda: (
            chart.read_bars(page)["third"],
            chart.read_stored(check.instance, project)[0]["third"],
        ),
        ((chart.day(10), chart.day(10), True), (chart.day(10), chart.day(10), True)),
    )

    writes.clear()
    control = chart.open_arrow_control(page, "second", "fourth")
    control.get_by_role("button", name="Remove the arrow").click()
    check.expect(
        "the removal closes the control and removes the arrow, in one request, and the task it led to is fixed on "
        "the days it stood on",
        lambda: (
            chart.read_control(page),
            chart.read_arrows(page),
            chart.read_stored(check.instance, project)[0]["fourth"],
            len(browser.read_writes(page, writes)),
        ),
        (
            None,
            [("first", "second", "end-start"), ("second", "third", "end-start")],
            (chart.day(11), chart.day(12), True),
            1,
        ),
    )

    stored = chart.read_stored(check.instance, project)
    control = chart.open_arrow_control(page, "second", "third")
    control.get_by_label("Delay in days").click()
    page.keyboard.press("End")
    page.keyboard.press("Delete")
    page.keyboard.press("Backspace")
    check.expect_stays(
        "Delete and Backspace typed in the number remove no arrow, and the control stays open",
        lambda: (chart.read_control(page) is not None, chart.read_arrows(page)),
        (True, [("first", "second", "end-start"), ("second", "third", "end-start")]),
    )
    page.keyboard.press("Escape")
    control = chart.open_arrow_control(page, "second", "third")
    page.keyboard.press("Backspace")
    check.expect_stays(
        "Backspace on the selected arrow leaves it, selected, with its control open",
        lambda: (
            chart.read_control(page) is not None,
            chart.read_arrow_looks(page)[("second", "third")][1],
            chart.read_stored(check.instance, project),
        ),
        (True, "selected", stored),
    )
    page.keyboard.press("Delete")
    check.expect(
        "Delete on the selected arrow removes it and closes the control",
        lambda: (
            chart.read_control(page),
            chart.read_arrows(page),
            read_stored_arrows(check, project),
        ),
        (
            None,
            [("first", "second", "end-start")],
            [("first", "second", "end-start", 7)],
        ),
    )
    browser.let_page_draw(page)
    page.context.close()
