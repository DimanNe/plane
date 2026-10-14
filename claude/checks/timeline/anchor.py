"""
A task carried from the list takes an edge of a bar as its anchor when the pointer comes near that edge slowly. It
then follows a new arrow from that edge, linked at the edge and "in ≥ n d" when the pointer is n days to the right
of it, and the edge is marked. The anchor is kept wherever the pointer goes, lost to the left of the edge, and
taken by another edge the pointer comes near slowly. Let go, the task, the arrow and its delay are stored in one
request; Escape stores nothing. A pointer that passes an edge fast takes no anchor.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps


def read_carried(
    page: pw.Page,
) -> t.Tuple[
    chart.Task, t.List[t.Tuple[str, str, str]], t.Optional[str], t.List[t.List[str]]
]:
    """The carried task as the chart draws it: its days, the arrows to it, the text over them, the marked edge."""
    return (
        chart.read_bars(page)["carried"],
        [arrow for arrow in chart.read_arrows(page) if arrow[1] == "carried"],
        next(
            (
                said
                for (_, following), said in chart.read_texts(page).items()
                if following == "carried"
            ),
            None,
        ),
        chart.read_marked_handles(page),
    )


def read_stored_carried(
    check: steps.Check, project: ins.Project
) -> t.Tuple[chart.Task, t.List[chart.Arrow]]:
    tasks: t.Dict[str, chart.Task]
    arrows: t.List[chart.Arrow]
    tasks, arrows = chart.read_stored(check.instance, project)
    return tasks["carried"], [arrow for arrow in arrows if arrow[1] == "carried"]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "before", "start_date": chart.day(1), "target_date": chart.day(3)},
            {"name": "other", "start_date": chart.day(7), "target_date": chart.day(9)},
            {"name": "carried"},
            {"name": "escaped"},
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project)
    writes: t.List[str] = browser.record_writes(page)
    px_per_day: float = chart.get_px_per_day(page)
    end_x: float = chart.get_edge_x(page, "before", "end")
    before_y: float = chart.get_line_y(page, "before")
    own_y: float = chart.get_line_y(page, "carried")

    chart.carry_entry(page, "carried")
    page.mouse.move(end_x + 8, before_y, steps=10)
    browser.let_page_draw(page)
    check.expect(
        "carried fast to 8 px beside the end of a bar, the task takes no anchor: it stands fixed on the day under "
        "the pointer, with no arrow",
        lambda: read_carried(page),
        ((chart.day(4), chart.day(4), True), [], None, []),
    )
    chart.move_slowly(page, (end_x + 8, before_y), (end_x + 3, before_y))
    check.expect(
        "moved on slowly, near the end: the task follows a new arrow from that end, linked to it, and the end is "
        "marked",
        lambda: read_carried(page),
        (
            (chart.day(4), chart.day(4), False),
            [("before", "carried", "end-start")],
            "linked",
            [["before", "end", "takes"]],
        ),
    )
    days: int
    for days in (1, 2, 5):
        page.mouse.move(end_x + 3 + days * px_per_day, before_y, steps=3)
        check.expect(
            f"the pointer {days} days to the right of the end: the arrow asks for {days} days and says so",
            lambda: read_carried(page)[:3],
            (
                (chart.day(4 + days), chart.day(4 + days), False),
                [("before", "carried", "end-start")],
                f"in ≥ {days} d",
            ),
        )
    page.mouse.move(end_x + 3 + 5 * px_per_day, own_y, steps=6)
    check.expect(
        "the pointer goes down to the task's own line: the anchor is kept",
        lambda: read_carried(page),
        (
            (chart.day(9), chart.day(9), False),
            [("before", "carried", "end-start")],
            "in ≥ 5 d",
            [["before", "end", "takes"]],
        ),
    )
    page.mouse.move(end_x - 12, own_y, steps=6)
    check.expect(
        "12 px to the left of the end: still anchored, linked",
        lambda: read_carried(page)[:3],
        (
            (chart.day(4), chart.day(4), False),
            [("before", "carried", "end-start")],
            "linked",
        ),
    )
    page.mouse.move(end_x - 20 - 2 * px_per_day, own_y, steps=6)
    check.expect(
        "further to the left than the reach of the edge: the anchor is lost, the task stands fixed on the day under "
        "the pointer, and nothing is marked",
        lambda: read_carried(page),
        ((chart.day(1), chart.day(1), True), [], None, []),
    )
    check.expect(
        "nothing is sent while the task is carried",
        lambda: (
            read_stored_carried(check, project),
            browser.read_writes(page, writes),
        ),
        (((None, None, None), []), []),
    )

    start_x: float = chart.get_edge_x(page, "other", "start")
    other_y: float = chart.get_line_y(page, "other")
    page.mouse.move(start_x + 30, other_y, steps=6)
    chart.move_slowly(page, (start_x + 30, other_y), (start_x + 3, other_y))
    check.expect(
        "slowly to the start of another bar: the task follows a new arrow from that start, from start to start",
        lambda: read_carried(page),
        (
            (chart.day(7), chart.day(7), False),
            [("other", "carried", "start-start")],
            "linked",
            [["other", "start", "takes"]],
        ),
    )
    page.mouse.move(start_x + 3 + 2 * px_per_day, own_y, steps=4)
    browser.let_page_draw(page)
    page.mouse.up()
    check.expect(
        "let go two days to the right of it: the task, the arrow and its delay are stored, the task following the "
        "arrow, in one request",
        lambda: (
            read_stored_carried(check, project),
            len(browser.read_writes(page, writes)),
        ),
        (
            (
                (chart.day(9), chart.day(9), False),
                [("other", "carried", "start-start", 2)],
            ),
            1,
        ),
    )
    check.expect(
        "and the chart shows it, with no mark",
        lambda: read_carried(page),
        (
            (chart.day(9), chart.day(9), False),
            [("other", "carried", "start-start")],
            "in ≥ 2 d",
            [],
        ),
    )

    writes.clear()
    chart.carry_entry(page, "escaped")
    page.mouse.move(end_x + 30, before_y, steps=6)
    chart.move_slowly(page, (end_x + 30, before_y), (end_x + 3, before_y))
    check.expect(
        "another task carried slowly to the same end takes it as its anchor too",
        lambda: (
            chart.read_bars(page)["escaped"],
            ("before", "escaped", "end-start") in chart.read_arrows(page),
            chart.read_marked_handles(page),
        ),
        ((chart.day(4), chart.day(4), False), True, [["before", "end", "takes"]]),
    )
    page.keyboard.press("Escape")
    page.mouse.up()
    check.expect(
        "Escape: the task has no bar again, no arrow leads to it, and nothing is marked",
        lambda: (
            chart.read_bars(page)["escaped"],
            [arrow for arrow in chart.read_arrows(page) if arrow[1] == "escaped"],
            chart.read_marked_handles(page),
        ),
        ((None, None, None), [], []),
    )
    # the rule is that nothing comes after Escape, so the step gives the page the time to send it
    check.expect_stays(
        "and nothing is sent",
        lambda: browser.read_writes(page, browser.read_writes(page, writes)),
        [],
        seconds=1,
    )
    page.context.close()
