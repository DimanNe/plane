"""
An arrow is drawn from a handle at an edge of one bar to a handle of another: from an end to a start, from a start
to a start, or from an end to an end, with the days there are between the two edges, and its next task then follows
it. While it is drawn the chart shows it and the handle under the pointer is marked. Each is stored on release in
one request; Escape stores nothing, nor does a release over no handle.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps


def read_drawing(
    page: pw.Page,
) -> t.Tuple[
    t.List[chart.DrawnArrow],
    t.Dict[t.Tuple[str, str], str],
    t.List[t.List[str]],
    t.List[str],
]:
    """What the chart shows while an arrow is drawn: the arrows, the texts over them, the marked handles and the
    texts that say why a handle does not take the arrow."""
    return (
        chart.read_arrows(page),
        chart.read_texts(page),
        chart.read_marked_handles(page),
        chart.read_refusals(page),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(1), "target_date": chart.day(3)},
            {"name": "second", "start_date": chart.day(8), "target_date": chart.day(8)},
            {"name": "third", "start_date": chart.day(5), "target_date": chart.day(9)},
            {"name": "fourth", "start_date": chart.day(2), "target_date": chart.day(4)},
        ],
        [("first", "third", "end-start", 1)],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=1)
    writes: t.List[str] = browser.record_writes(page)
    stored: t.Tuple[t.Dict[str, chart.Task], t.List[chart.Arrow]] = chart.read_stored(
        check.instance, project
    )

    chart.draw_arrow(
        page,
        chart.get_handle_point(page, "first", "end"),
        chart.get_handle_point(page, "second", "start"),
    )
    check.expect(
        "an arrow drawn from the end of a bar to the start of another is drawn with the days there are, the start "
        "it is held over is marked, and nothing is refused",
        lambda: read_drawing(page),
        (
            [("first", "second", "end-start"), ("first", "third", "end-start")],
            {("first", "second"): "in ≥ 4 d"},
            [["second", "start", "takes"]],
            [],
        ),
    )
    check.expect(
        "its next task follows it while it is drawn, on its day, and nothing is sent",
        lambda: (chart.read_bars(page)["second"], browser.read_writes(page, writes)),
        ((chart.day(8), chart.day(8), False), []),
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    check.expect_stays(
        "after Escape the arrow is gone and nothing is stored",
        lambda: (
            chart.read_arrows(page),
            chart.read_stored(check.instance, project),
            browser.read_writes(page, writes),
        ),
        ([("first", "third", "end-start")], stored, []),
    )
    chart.draw_arrow(
        page, chart.get_handle_point(page, "first", "end"), chart.find_empty_point(page)
    )
    chart.let_go(page)
    check.expect_stays(
        "an arrow let go over no handle is not stored",
        lambda: (
            chart.read_arrows(page),
            chart.read_stored(check.instance, project),
            browser.read_writes(page, writes),
        ),
        ([("first", "third", "end-start")], stored, []),
    )

    chart.draw_arrow(
        page,
        chart.get_handle_point(page, "first", "end"),
        chart.get_handle_point(page, "second", "start"),
    )
    chart.let_go(page)
    check.expect(
        "let go on the handle, it is stored from end to start, in ≥ 4 d, and its next task follows it, in one "
        "request",
        lambda: (
            chart.read_stored(check.instance, project),
            len(browser.read_writes(page, writes)),
        ),
        (
            (
                {**stored[0], "second": (chart.day(8), chart.day(8), False)},
                [
                    ("first", "second", "end-start", 4),
                    ("first", "third", "end-start", 1),
                ],
            ),
            1,
        ),
    )
    chart.draw_arrow(
        page,
        chart.get_handle_point(page, "fourth", "start"),
        chart.get_half_point(page, "third", "start"),
    )
    chart.let_go(page)
    check.expect(
        "an arrow from a start to a start is stored with the days there are, and its next task follows its arrows "
        "where it stood",
        lambda: [
            arrow
            for arrow in chart.read_stored(check.instance, project)[1]
            if arrow[0] == "fourth"
        ],
        [("fourth", "third", "start-start", 3)],
    )
    chart.draw_arrow(
        page,
        chart.get_handle_point(page, "fourth", "end"),
        chart.get_half_point(page, "second", "end"),
    )
    chart.let_go(page)
    check.expect(
        "so is an arrow from an end to an end",
        lambda: chart.read_stored(check.instance, project),
        (
            {
                **stored[0],
                "second": (chart.day(8), chart.day(8), False),
                "third": (chart.day(5), chart.day(9), False),
            },
            [
                ("first", "second", "end-start", 4),
                ("first", "third", "end-start", 1),
                ("fourth", "second", "end-end", 4),
                ("fourth", "third", "start-start", 3),
            ],
        ),
    )
    check.expect(
        "the chart draws the four arrows and their texts",
        lambda: (chart.read_arrows(page), chart.read_texts(page)),
        (
            [
                ("first", "second", "end-start"),
                ("first", "third", "end-start"),
                ("fourth", "second", "end-end"),
                ("fourth", "third", "start-start"),
            ],
            {
                ("first", "second"): "in ≥ 4 d",
                ("first", "third"): "in ≥ 1 d",
                ("fourth", "second"): "in ≥ 4 d",
                ("fourth", "third"): "in ≥ 3 d",
            },
        ),
    )
    page.context.close()
