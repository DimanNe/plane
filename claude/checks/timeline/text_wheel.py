"""
The text over an arrow says what the arrow is in two parts, and the wheel turns each: on its days, a day a notch, no
fewer than none; on what the arrow is, the round of "in", "on" the day the next task stands on, and "linked". The
plan follows at once, the text stays under the pointer and the chart is not zoomed; the turns are one operation,
stored in one request when the wheel has rested or the pointer has left the text, and dropped by Escape. Within a
margin around the text the wheel turns the part nearest to it; further away it zooms the chart.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps

ARROW: t.Tuple[str, str] = ("first", "second")


def get_middle(box: t.Sequence[float]) -> browser.Point:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def read_turn(
    page: pw.Page, point: browser.Point
) -> t.Tuple[t.Optional[str], chart.Task, float]:
    """What the text under the pointer says, where the next task stands, and the scale of the chart."""
    return (
        chart.read_text_at(page, point),
        chart.read_bars(page)["second"],
        chart.get_px_per_day(page),
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
        ],
        [("first", "second", "end-start", 2)],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=1)
    writes: t.List[str] = browser.record_writes(page)
    px_per_day: float = chart.get_px_per_day(page)
    stored: t.Tuple[t.Dict[str, chart.Task], t.List[chart.Arrow]] = chart.read_stored(
        check.instance, project
    )
    check.expect(
        "the arrow says what it is in two parts",
        lambda: page.evaluate(
            chart.make_js("return textsOverArrows().map(({ parts }) => parts);")
        ),
        [["in", "≥ 2 d"]],
    )

    days: browser.Point = chart.get_part_point(page, *ARROW, 1)
    chart.turn_wheel(page, days, 1)
    check.expect(
        "a notch up on its days: in ≥ 3 d under the pointer, the next task a day later, the chart not zoomed, and "
        "nothing sent",
        lambda: (*read_turn(page, days), browser.read_writes(page, writes)),
        ("in ≥ 3 d", (chart.day(6), chart.day(8), False), px_per_day, []),
    )
    chart.turn_wheel(page, days, -5)
    check.expect(
        "five notches down: the days stop at none",
        lambda: read_turn(page, days),
        ("in ≥ 0 d", (chart.day(3), chart.day(5), False), px_per_day),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape puts the arrow and the task back",
        lambda: read_turn(page, days),
        ("in ≥ 2 d", (chart.day(5), chart.day(7), False), px_per_day),
    )

    kind: browser.Point = chart.get_part_point(page, *ARROW, 0)
    said: t.List[t.Tuple[t.Optional[str], chart.Task]] = []
    _: int
    for _ in range(3):
        chart.turn_wheel(page, kind, 1)
        said.append(read_turn(page, kind)[:2])
    check.expect(
        "notches up on what the arrow is: on the day it stands on, fixed there; then linked, at the edge; then in "
        "≥ 0 d, which moves nothing",
        lambda: said,
        [
            (
                f"on {chart.format_day(chart.day(5))}",
                (chart.day(5), chart.day(7), True),
            ),
            ("linked", (chart.day(3), chart.day(5), False)),
            ("in ≥ 0 d", (chart.day(3), chart.day(5), False)),
        ],
    )
    page.keyboard.press("Escape")
    check.expect_stays(
        "Escape puts everything back, and nothing was sent",
        lambda: (
            *read_turn(page, kind),
            chart.read_stored(check.instance, project),
            browser.read_writes(page, writes),
        ),
        ("in ≥ 2 d", (chart.day(5), chart.day(7), False), px_per_day, stored, []),
    )
    said = []
    for _ in range(3):
        chart.turn_wheel(page, kind, -1)
        said.append(read_turn(page, kind)[:2])
    check.expect(
        "notches down go the other way: linked, on, in",
        lambda: [text for text, _ in said],
        ["linked", f"on {chart.format_day(chart.day(3))}", "in ≥ 0 d"],
    )
    page.keyboard.press("Escape")

    chart.turn_wheel(page, kind, 2)
    check.expect(
        "two notches up and the wheel rests: stored as linked, the task at the edge, in one request",
        lambda: (
            chart.read_stored(check.instance, project),
            len(browser.read_writes(page, writes)),
        ),
        (
            (
                {**stored[0], "second": (chart.day(3), chart.day(5), False)},
                [("first", "second", "end-start", None)],
            ),
            1,
        ),
    )
    check.expect(
        "the text under the pointer says linked, in one part",
        lambda: chart.read_text_at(page, kind),
        "linked",
    )

    writes.clear()
    chart.turn_wheel(page, kind, 1)
    page.mouse.move(*chart.find_empty_point(page), steps=4)
    check.expect(
        "a notch and the pointer leaves the text: stored at once, in ≥ 0 d, which is not linked",
        lambda: (
            chart.read_stored(check.instance, project)[1],
            len(browser.read_writes(page, writes)),
        ),
        ([("first", "second", "end-start", 0)], 1),
    )

    box = chart.get_text_boxes(page, *ARROW)[0]
    middle: browser.Point = get_middle(box)
    chart.turn_wheel(page, (box[0] - 28, middle[1]), 1)
    check.expect(
        "the wheel 28 px left of the text turns what the arrow is, nearest there",
        lambda: (chart.read_text_at(page, middle), chart.get_px_per_day(page)),
        (f"on {chart.format_day(chart.day(3))}", px_per_day),
    )
    page.keyboard.press("Escape")
    page.mouse.move(*chart.find_empty_point(page), steps=4)
    chart.turn_wheel(page, (box[2] + 28, middle[1]), 1)
    check.expect(
        "28 px right of it, the days, nearest there",
        lambda: (chart.read_text_at(page, middle), chart.get_px_per_day(page)),
        ("in ≥ 1 d", px_per_day),
    )
    page.keyboard.press("Escape")
    page.mouse.move(*chart.find_empty_point(page), steps=4)
    writes.clear()
    chart.turn_wheel(page, chart.find_empty_point(page), 1)
    check.expect(
        "away from the text the wheel zooms the chart in, and the arrow stays",
        lambda: (
            chart.get_px_per_day(page) > px_per_day,
            chart.read_texts(page).get(ARROW),
        ),
        (True, "in ≥ 0 d"),
    )
    check.expect_stays(
        "and nothing is sent",
        lambda: browser.read_writes(page, writes),
        [],
    )
    page.context.close()
