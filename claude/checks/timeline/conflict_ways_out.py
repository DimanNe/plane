"""
Each way out of a conflict that its card offers is stored by a click, in one request, and leaves no conflict: let
the task follow its arrows, fix it on the day asked for, shorten the delay when that alone would do, remove the
arrow.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps
import timeline_conflict as tc


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    way: str
    late: chart.Task
    delay: t.Optional[int]
    for way, late, delay in (
        (f"Fix it on {tc.write_day(7)}", (chart.day(7), chart.day(9), True), 2),
        ("Let it follow its arrows", (chart.day(7), chart.day(9), False), 2),
        ("Shorten the delay to 0 d", (chart.day(5), chart.day(7), True), 0),
        ("Remove this arrow", (chart.day(5), chart.day(7), True), None),
    ):
        project: ins.Project
        page: pw.Page
        writes: t.List[str]
        project, page, writes = tc.take_way_out(check, account, way)
        arrows: t.List[chart.Arrow] = [("first", "middle", "end-start", 1)]
        if way != "Remove this arrow":
            arrows.append(("middle", "late", "end-start", delay))
        check.expect(
            f"{way}: stored in one request, and no conflict is left",
            lambda: (
                chart.read_stored(check.instance, project),
                len(browser.read_writes(page, writes)),
                tc.read_red(page),
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
