"""
A task is put on the chart by carrying its name from the list at the left onto the chart: it starts on the day
under the pointer, fixed there, one day long unless it had dates, and is stored in one request. Carried back over
the list, or dropped with Escape, it is put nowhere. A click on the empty line of a task without dates puts it
nowhere either. The name of a task that is not on the chart is muted.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps

MUTED_JS: str = chart.make_js(
    """return lines().filter((line) => line.firstElementChild.querySelector('span.truncate')
          .classList.contains('text-tertiary')).map(nameOf);"""
)


def read_muted(page: pw.Page) -> t.List[str]:
    return page.evaluate(MUTED_JS)


def read_task(
    check: steps.Check, project: ins.Project, page: pw.Page, name: str
) -> t.Tuple[chart.Task, chart.Task]:
    """A task as the chart draws it and as the server has it."""
    return (
        chart.read_bars(page)[name],
        chart.read_stored(check.instance, project)[0][name],
    )


def carry_to_day(page: pw.Page, name: str, date: str) -> None:
    """Carries a task's name from the list to the middle of a day, on the task's own line."""
    chart.carry_entry(page, name)
    page.mouse.move(
        chart.get_day_x(page, date, 0.5), chart.get_line_y(page, name), steps=8
    )
    browser.let_page_draw(page)


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {
                "name": "on the chart",
                "start_date": chart.day(1),
                "target_date": chart.day(3),
            },
            {"name": "without dates"},
            {"name": "carried back"},
            {"name": "dropped"},
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project)
    check.expect(
        "the names of the tasks that are not on the chart are muted, and only those",
        lambda: read_muted(page),
        ["without dates", "carried back", "dropped"],
    )
    writes: t.List[str] = browser.record_writes(page)

    carry_to_day(page, "without dates", chart.day(6))
    check.expect(
        "a task without dates carried onto the chart stands on the day under the pointer, one day long, fixed, and "
        "nothing is sent while it is carried",
        lambda: (
            read_task(check, project, page, "without dates"),
            browser.read_writes(page, writes),
        ),
        (((chart.day(6), chart.day(6), True), (None, None, None)), []),
    )
    page.mouse.up()
    check.expect(
        "let go, it is stored there in one request",
        lambda: (
            read_task(check, project, page, "without dates"),
            len(browser.read_writes(page, writes)),
        ),
        (((chart.day(6), chart.day(6), True), (chart.day(6), chart.day(6), True)), 1),
    )
    check.expect(
        "and its name is not muted any more",
        lambda: read_muted(page),
        ["carried back", "dropped"],
    )

    carry_to_day(page, "on the chart", chart.day(8))
    page.mouse.up()
    check.expect(
        "a task with dates carried by its name starts on the day under the pointer and keeps its length",
        lambda: read_task(check, project, page, "on the chart"),
        ((chart.day(8), chart.day(10), True), (chart.day(8), chart.day(10), True)),
    )

    writes.clear()
    carry_to_day(page, "carried back", chart.day(4))
    page.mouse.move(*chart.get_entry_point(page, "carried back"), steps=8)
    browser.let_page_draw(page)
    check.expect(
        "carried back over the list, the task has no bar",
        lambda: chart.read_bars(page)["carried back"],
        (None, None, None),
    )
    page.mouse.up()
    carry_to_day(page, "dropped", chart.day(4))
    page.keyboard.press("Escape")
    page.mouse.up()
    # the rule is that nothing comes, so the step gives the page the time to send it
    check.expect_stays(
        "let go over the list, or after Escape, a task is put nowhere and nothing is sent",
        lambda: (
            read_task(check, project, page, "carried back"),
            read_task(check, project, page, "dropped"),
            browser.read_writes(page, browser.read_writes(page, writes)),
        ),
        (
            ((None, None, None), (None, None, None)),
            ((None, None, None), (None, None, None)),
            [],
        ),
        seconds=1,
    )

    page.mouse.click(
        chart.get_day_x(page, chart.day(4), 0.5), chart.get_line_y(page, "dropped")
    )
    check.expect_stays(
        "a click on the empty line of a task without dates puts it nowhere",
        lambda: (
            read_task(check, project, page, "dropped"),
            browser.read_writes(page, writes),
        ),
        (((None, None, None), (None, None, None)), []),
        seconds=1,
    )
    page.context.close()
