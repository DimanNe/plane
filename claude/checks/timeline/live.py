"""
An open timeline draws a change of its plan made elsewhere, without being loaded again: a task that another
session made follow its arrow, with days, stands where the arrow puts it, and the arrow says its days.
"""

import typing as t

import playwright.sync_api as pw

import chart
import instance as ins
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(0), "target_date": chart.day(2)},
            {"name": "second", "start_date": chart.day(4), "target_date": chart.day(6)},
        ],
        [("first", "second", "end-start", 0)],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=1)
    check.expect(
        "the second task is fixed on its day, and the arrow is a check with no text over it",
        lambda: (chart.read_bars(page)["second"], chart.read_texts(page)),
        ((chart.day(4), chart.day(6), True), {}),
    )
    path: str = f"/projects/{project.id}/work-items/{ids['first']}/dependencies/{ids['second']}/"
    ins.call_api(check.instance, "DELETE", path)
    chart.make_arrows(
        check.instance, project, ids, [("first", "second", "end-start", 3)]
    )
    ins.call_api(
        check.instance,
        "PATCH",
        f"/projects/{project.id}/work-items/{ids['second']}/",
        {"is_start_fixed": False},
    )
    check.expect(
        "another session makes it follow the arrow in ≥ 3 d: it stands where the arrow puts it, and the arrow says "
        "its days",
        lambda: (chart.read_bars(page)["second"], chart.read_texts(page)),
        ((chart.day(6), chart.day(8), False), {("first", "second"): "in ≥ 3 d"}),
    )
    check.expect(
        "and the page stores the dates the arrow gives it",
        lambda: chart.read_stored(check.instance, project)[0]["second"],
        (chart.day(6), chart.day(8), False),
    )
    page.context.close()
