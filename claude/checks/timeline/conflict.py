"""
An arrow that asks a task fixed on its day to start later than that day is a conflict: it is red, and its text says
in red by how many days the task is too early. Under the pointer a card explains it, with the tasks and the arrows
that produce it ringed in red, and offers the ways out: let the task follow its arrows, fix it on the day asked for,
shorten the delay when that alone would do, remove the arrow; each is stored by a click, in one request. A link
whose next task stands later than the link puts it is apart: red, with its card and its ways out.
"""

import datetime as dt
import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps


def write_day(offset: int) -> str:
    """A day as the card writes it."""
    date: dt.date = dt.date.fromisoformat(chart.day(offset))
    return f"{date:%b} {date.day}"


def open_conflict(
    check: steps.Check, account: ins.Account
) -> t.Tuple[ins.Project, pw.Page]:
    """A task that follows another by a day, and a task fixed two days earlier than the arrow from it asks."""
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(0), "target_date": chart.day(1)},
            {
                "name": "middle",
                "start_date": chart.day(3),
                "target_date": chart.day(4),
                "is_start_fixed": False,
            },
            {"name": "late", "start_date": chart.day(5), "target_date": chart.day(7)},
        ],
        [("first", "middle", "end-start", 1), ("middle", "late", "end-start", 2)],
    )
    return project, chart.open_timeline(check, account, project, arrows=2)


def read_red(page: pw.Page) -> t.Tuple[t.List[t.Tuple[str, str]], t.List[str]]:
    """The arrows drawn red, and the tasks ringed red."""
    return (
        sorted(
            arrow
            for arrow, (colour, _) in chart.read_arrow_looks(page).items()
            if colour == "danger"
        ),
        chart.read_ringed(page, "danger"),
    )


def take_way_out(
    check: steps.Check, account: ins.Account, way: str
) -> t.Tuple[ins.Project, pw.Page, t.List[str]]:
    """The conflict opened again, and a way out of its card clicked; the requests the click sent."""
    project: ins.Project
    page: pw.Page
    project, page = open_conflict(check, account)
    # the pointer on the conflict's text, which the card stands by, once the text has found its place
    page.locator('div[class~="z-[3]"] [class~="text-11"]').filter(
        has_text="too early"
    ).first.hover()
    page.locator(chart.CARD).get_by_role("button", name=way).wait_for()
    writes: t.List[str] = browser.record_writes(page)
    page.locator(chart.CARD).get_by_role("button", name=way).click()
    return project, page, writes


def check_ways_out(check: steps.Check, account: ins.Account) -> None:
    way: str
    late: chart.Task
    delay: t.Optional[int]
    for way, late, delay in (
        (f"Fix it on {write_day(7)}", (chart.day(7), chart.day(9), True), 2),
        ("Let it follow its arrows", (chart.day(7), chart.day(9), False), 2),
        ("Shorten the delay to 0 d", (chart.day(5), chart.day(7), True), 0),
        ("Remove this arrow", (chart.day(5), chart.day(7), True), None),
    ):
        project: ins.Project
        page: pw.Page
        writes: t.List[str]
        project, page, writes = take_way_out(check, account, way)
        arrows: t.List[chart.Arrow] = [("first", "middle", "end-start", 1)]
        if way != "Remove this arrow":
            arrows.append(("middle", "late", "end-start", delay))
        check.expect(
            f"{way}: stored in one request, and no conflict is left",
            lambda: (
                chart.read_stored(check.instance, project),
                len(browser.read_writes(page, writes)),
                read_red(page),
            ),
            (
                (
                    {
                        "first": (chart.day(0), chart.day(1), True),
                        "middle": (chart.day(3), chart.day(4), False),
                        "late": late,
                    },
                    arrows,
                ),
                1,
                ([], []),
            ),
        )
        page.context.close()


def check_apart_link(check: steps.Check, account: ins.Account) -> None:
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {
                "name": "linking",
                "start_date": chart.day(0),
                "target_date": chart.day(1),
            },
            {"name": "asking", "start_date": chart.day(0), "target_date": chart.day(2)},
            {
                "name": "next",
                "start_date": chart.day(6),
                "target_date": chart.day(6),
                "is_start_fixed": False,
            },
        ],
        [("linking", "next", "end-start", None), ("asking", "next", "end-start", 3)],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=2)
    check.expect(
        "a link whose next task another arrow holds four days later is apart: red, and its text says by how many days",
        lambda: (
            chart.read_texts(page).get(("linking", "next")),
            chart.read_text_looks(page).get(("linking", "next"), (None,))[0],
            chart.read_arrow_looks(page)[("linking", "next")][0],
        ),
        ("linked 4 d apart", True, "danger"),
    )
    chart.hover_arrow(page, "linking", "next", 0.4)
    check.expect(
        "under the pointer its card explains it and offers its ways out",
        lambda: chart.read_card(page),
        [
            "next is linked to linking, but stands 4 days later than the link puts it: the arrow from asking asks for "
            "that.",
            ["Make this arrow in ≥ 4 d", "Remove this arrow"],
        ],
    )
    page.locator(chart.CARD).get_by_role(
        "button", name="Make this arrow in ≥ 4 d"
    ).click()
    check.expect(
        "a click on the first: the arrow is in ≥ 4 d, stored, and it is red no more",
        lambda: (
            chart.read_stored(check.instance, project)[1],
            chart.read_arrow_looks(page)[("linking", "next")][0] == "danger",
        ),
        (
            [("asking", "next", "end-start", 3), ("linking", "next", "end-start", 4)],
            False,
        ),
    )
    page.context.close()


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project
    page: pw.Page
    project, page = open_conflict(check, account)
    check.expect(
        "the arrow that asks a fixed task to start later is red, and so is its text, which says by how many days the "
        "task is too early; the other arrow says its days",
        lambda: (
            read_red(page)[0],
            chart.read_texts(page),
            chart.read_text_looks(page)[("middle", "late")][0],
        ),
        (
            [("middle", "late")],
            {("first", "middle"): "in ≥ 1 d", ("middle", "late"): "2 d too early"},
            True,
        ),
    )
    check.expect(
        "no card is shown without the pointer", lambda: chart.read_card(page), None
    )
    chart.hover_arrow(page, "middle", "late", 0.4)
    check.expect(
        "under the pointer the card says which task is fixed on which day and what the arrow asks for and why, and "
        "offers the ways out",
        lambda: chart.read_card(page),
        [
            f"late is fixed on {write_day(5)}. This arrow asks it to start no earlier than {write_day(7)}: 2 days "
            f"after middle ends on {write_day(4)}.",
            [
                "Let it follow its arrows",
                f"Fix it on {write_day(7)}",
                "Shorten the delay to 0 d",
                "Remove this arrow",
            ],
        ],
    )
    check.expect(
        "the tasks and the arrows that produce it, back to a fixed task, are red",
        lambda: read_red(page),
        ([("first", "middle"), ("middle", "late")], ["first", "middle", "late"]),
    )
    page.mouse.move(*chart.find_empty_point(page), steps=4)
    check.expect(
        "away from the arrow the card and the rings go, and the texts stay",
        lambda: (chart.read_card(page), read_red(page), len(chart.read_texts(page))),
        (None, ([("middle", "late")], []), 2),
    )
    page.context.close()
    check_ways_out(check, account)
    check_apart_link(check, account)
