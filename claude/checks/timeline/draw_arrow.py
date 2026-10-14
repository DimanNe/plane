"""
An arrow is drawn from a handle at an edge of one bar to a handle of another: from an end to a start, from a start
to a start, or from an end to an end, with the days there are between the two edges, and its next task then follows
it. While it is drawn the chart shows it and the handle under the pointer is marked; a handle that does not take it
is marked red and a text says why, and nothing is stored. An end of an arrow taken to the other handle of its bar
changes the arrow's kind. Each is stored on release in one request; Escape stores nothing.
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


def draw(page: pw.Page, start: browser.Point, end: browser.Point) -> None:
    """Presses at a point, which shows the handles of the bar there, and draws to another point."""
    page.mouse.move(*start)
    browser.let_page_draw(page)
    chart.drag(page, start, end)


def check_refusals(
    check: steps.Check, page: pw.Page, project: ins.Project, writes: t.List[str]
) -> None:
    stored: t.Tuple[t.Dict[str, chart.Task], t.List[chart.Arrow]] = chart.read_stored(
        check.instance, project
    )
    drawn: t.Tuple[t.Dict[str, chart.Task], t.List[chart.DrawnArrow]] = chart.read_plan(
        page
    )
    way: str
    source: t.Tuple[str, str]
    target: t.Tuple[str, str]
    said: str
    for way, source, target, said in (
        (
            "from a start to an end",
            ("first", "start"),
            ("fourth", "end"),
            "No arrow runs from a start to an end",
        ),
        (
            "to the same task",
            ("first", "start"),
            ("first", "end"),
            "An arrow goes from one task to another",
        ),
        (
            "between tasks that are connected",
            ("first", "end"),
            ("third", "start"),
            "These tasks are connected already",
        ),
        (
            "that closes a loop",
            ("third", "end"),
            ("first", "start"),
            "This arrow would close a loop",
        ),
    ):
        draw(
            page,
            chart.get_handle_point(page, *source),
            chart.get_half_point(page, *target),
        )
        check.expect(
            f"an arrow {way}: the handle under the pointer is marked red, a text says why, and the plan is drawn "
            f"as it was",
            lambda: (
                chart.read_marked_handles(page),
                chart.read_refusals(page),
                chart.read_plan(page),
            ),
            ([[target[0], target[1], "refuses"]], [said], drawn),
        )
        chart.let_go(page)
        # the rule is that nothing comes, so the step gives the page the time to send it
        check.expect_stays(
            f"an arrow {way}, let go: nothing is stored and the text is gone",
            lambda: (
                chart.read_stored(check.instance, project),
                chart.read_refusals(page),
                browser.read_writes(page, writes),
            ),
            (stored, [], []),
            seconds=1,
        )


def check_ends(
    check: steps.Check, page: pw.Page, project: ins.Project, writes: t.List[str]
) -> None:
    writes.clear()
    stored: t.Tuple[t.Dict[str, chart.Task], t.List[chart.Arrow]] = chart.read_stored(
        check.instance, project
    )
    chart.drag(
        page,
        chart.get_arrow_end_point(page, "first", "third", "tail"),
        chart.get_half_point(page, "first", "start"),
    )
    check.expect(
        "the tail of an arrow from an end to a start taken to the start of its bar: the arrow is drawn from start "
        "to start",
        lambda: ("first", "third", "start-start") in chart.read_arrows(page),
        True,
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    check.expect_stays(
        "after Escape it is as it was, and nothing is sent",
        lambda: (
            ("first", "third", "end-start") in chart.read_arrows(page),
            chart.read_stored(check.instance, project),
            browser.read_writes(page, writes),
        ),
        (True, stored, []),
        seconds=1,
    )
    chart.drag(
        page,
        chart.get_arrow_end_point(page, "first", "third", "tail"),
        chart.get_half_point(page, "first", "start"),
    )
    chart.let_go(page)
    check.expect(
        "let go there, it is stored from start to start, in one request",
        lambda: (
            [
                arrow[:3]
                for arrow in chart.read_stored(check.instance, project)[1]
                if arrow[:2] == ("first", "third")
            ],
            len(browser.read_writes(page, writes)),
        ),
        ([("first", "third", "start-start")], 1),
    )
    chart.drag(
        page,
        chart.get_arrow_end_point(page, "first", "second", "head"),
        chart.get_half_point(page, "second", "end"),
    )
    chart.let_go(page)
    check.expect(
        "the head of an arrow from an end to a start taken to the end of its bar: it is stored from end to end",
        lambda: [
            arrow[:3]
            for arrow in chart.read_stored(check.instance, project)[1]
            if arrow[:2] == ("first", "second")
        ],
        [("first", "second", "end-end")],
    )
    stored = chart.read_stored(check.instance, project)
    writes.clear()
    chart.drag(
        page,
        chart.get_arrow_end_point(page, "first", "third", "head"),
        chart.get_half_point(page, "third", "end"),
    )
    check.expect(
        "the head of an arrow from a start to a start held at the end of its bar: the handle refuses it and says "
        "why",
        lambda: (chart.read_marked_handles(page), chart.read_refusals(page)),
        ([["third", "end", "refuses"]], ["No arrow runs from a start to an end"]),
    )
    chart.let_go(page)
    check.expect_stays(
        "let go, the arrow stays as it was, and nothing is sent",
        lambda: (
            ("first", "third", "start-start") in chart.read_arrows(page),
            chart.read_stored(check.instance, project),
            browser.read_writes(page, writes),
        ),
        (True, stored, []),
        seconds=1,
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

    draw(
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
        seconds=1,
    )
    draw(
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
        seconds=1,
    )

    draw(
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
    draw(
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
    draw(
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
    writes.clear()
    check_refusals(check, page, project, writes)
    check_ends(check, page, project, writes)
    page.context.close()
