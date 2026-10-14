"""
On the timeline a click on a bar, or on a task's name in the list, selects the task and opens nothing; a double
click opens the work item beside the timeline, which then shows whatever task is selected, and Escape closes it and
keeps the selection. A click on the empty part of a task's line changes nothing.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import list_layout as ll
import steps


def read_selection(page: pw.Page) -> t.Tuple[t.List[str], t.Optional[str]]:
    return chart.read_selected(page), ll.read_panel(page)


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(1), "target_date": chart.day(3)},
            {"name": "second", "start_date": chart.day(4), "target_date": chart.day(6)},
            {"name": "third", "start_date": chart.day(2), "target_date": chart.day(2)},
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project)
    writes: t.List[str] = browser.record_writes(page)
    check.expect(
        "nothing is selected when the timeline opens",
        lambda: read_selection(page),
        ([], None),
    )
    page.mouse.click(*chart.get_bar_point(page, "first"))
    check.expect(
        "a click on a bar selects its task and opens nothing",
        lambda: read_selection(page),
        (["first"], None),
    )
    page.mouse.dblclick(*chart.get_bar_point(page, "second"))
    check.expect(
        "a double click on a bar opens its work item beside the timeline",
        lambda: read_selection(page),
        (["second"], "second"),
    )
    # the view beside the timeline covers the chart, and leaves the list in view
    page.mouse.click(*chart.get_entry_point(page, "third"))
    check.expect(
        "while the work item is open, a click on another task's name shows that one",
        lambda: read_selection(page),
        (["third"], "third"),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes it and the selection stays",
        lambda: read_selection(page),
        (["third"], None),
    )
    page.mouse.click(*chart.get_entry_point(page, "first"))
    check.expect(
        "a click on a task's name in the list selects it and opens nothing",
        lambda: read_selection(page),
        (["first"], None),
    )

    page.mouse.click(
        chart.get_day_x(page, chart.day(9), 0.5), chart.get_line_y(page, "second")
    )
    # the rule is that nothing comes, so the step gives the page the time to do it
    check.expect_stays(
        "a click on the empty part of a task's line changes nothing",
        lambda: (
            read_selection(page),
            chart.read_bars(page)["second"],
            browser.read_writes(page, writes),
        ),
        ((["first"], None), (chart.day(4), chart.day(6), True), []),
        seconds=1,
    )
    page.context.close()
