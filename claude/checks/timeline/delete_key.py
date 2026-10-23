"""
Delete on the selected task of the timeline, selected on its bar or in the list, takes it off the chart in one
request: its dates are cleared, the arrows to it and from it are removed, and it is stored as fixed again, as a work
item that was never on the timeline. The work item stays, with its relations of other kinds, and no other task
moves: one that its arrow decided is fixed where it stood. Backspace does nothing, nor does Delete with nothing
selected, or on a task that is not on the chart.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps


def read_related(
    check: steps.Check, project: ins.Project, item_id: str
) -> t.Dict[str, t.List[str]]:
    """The work items related to one by a relation that is not the timeline's, by relation type."""
    relations: ins.JSONObject = ins.call_api(
        check.instance,
        "GET",
        f"/projects/{project.id}/work-items/{item_id}/work-item-relations/",
    )
    return {
        kind: sorted(item["name"] for item in items)
        for kind, items in relations.items()
        if items
    }


def read_is_fixed(check: steps.Check, project: ins.Project, name: str) -> bool:
    return ins.read_work_items(check.instance, project)[name]["is_start_fixed"]


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = chart.make_plan(
        check.instance,
        project,
        [
            {
                "name": "earlier",
                "start_date": chart.day(1),
                "target_date": chart.day(2),
            },
            {
                "name": "taken off",
                "start_date": chart.day(4),
                "target_date": chart.day(6),
                "is_start_fixed": False,
            },
            {
                "name": "after",
                "start_date": chart.day(7),
                "target_date": chart.day(8),
                "is_start_fixed": False,
            },
            {"name": "related"},
            {"name": "not placed"},
        ],
        [
            ("earlier", "taken off", "end-start", 1),
            ("taken off", "after", "end-start", 0),
            ("earlier", "after", "end-start", 0),
        ],
    )
    ins.call_app(
        check.instance.url,
        account,
        "POST",
        f"/workspaces/{check.instance.workspace}/projects/{project.id}/issues/{ids['taken off']}/issue-relation/",
        {"relation_type": "relates_to", "issues": [ids["related"]]},
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=3)
    stored_before: t.Tuple[t.Dict[str, chart.Task], t.List[chart.Arrow]] = (
        chart.read_stored(check.instance, project)
    )
    drawn: t.Tuple[t.Dict[str, chart.Task], t.List[chart.DrawnArrow]] = (
        {
            "earlier": (chart.day(1), chart.day(2), True),
            "taken off": (chart.day(4), chart.day(6), False),
            "after": (chart.day(7), chart.day(8), False),
            "related": (None, None, None),
            "not placed": (None, None, None),
        },
        [
            ("earlier", "after", "end-start"),
            ("earlier", "taken off", "end-start"),
            ("taken off", "after", "end-start"),
        ],
    )
    check.expect(
        "the chart shows the plan: the two tasks after the first stand where their arrows put them",
        lambda: chart.read_plan(page),
        drawn,
    )
    writes: t.List[str] = browser.record_writes(page)

    page.mouse.click(*chart.get_bar_point(page, "taken off"))
    check.expect(
        "a click on a bar selects its task",
        lambda: chart.read_selected(page),
        ["taken off"],
    )
    page.keyboard.press("Backspace")
    check.expect_stays(
        "Backspace takes nothing off the chart",
        lambda: (chart.read_plan(page), browser.read_writes(page, writes)),
        (drawn, []),
    )
    page.mouse.click(*chart.get_arrow_point(page, "earlier", "taken off"))
    check.expect(
        "a click on an arrow leaves no task selected",
        lambda: chart.read_selected(page),
        [],
    )
    page.keyboard.press("Escape")
    page.keyboard.press("Delete")
    check.expect_stays(
        "Delete with nothing selected takes nothing off",
        lambda: (chart.read_plan(page), browser.read_writes(page, writes)),
        (drawn, []),
    )

    page.mouse.click(*chart.get_bar_point(page, "taken off"))
    page.keyboard.press("Delete")
    check.expect(
        "Delete on the selected bar: the task's dates are cleared and its arrows removed, in one request",
        lambda: (
            chart.read_stored(check.instance, project),
            len(browser.read_writes(page, writes)),
        ),
        (
            (
                {
                    **stored_before[0],
                    "taken off": (None, None, None),
                    "after": (chart.day(7), chart.day(8), True),
                },
                [("earlier", "after", "end-start", 0)],
            ),
            1,
        ),
    )
    check.expect(
        "it is stored as fixed again, and the work item stays with its relation of another kind",
        lambda: (
            read_is_fixed(check, project, "taken off"),
            read_related(check, project, ids["taken off"]),
        ),
        (True, {"relates_to": ["related"]}),
    )
    check.expect(
        "the chart draws it with no bar and no arrow, its line still in the list, and the task its arrow decided "
        "fixed where it stood",
        lambda: chart.read_plan(page),
        (
            {
                "earlier": (chart.day(1), chart.day(2), True),
                "taken off": (None, None, None),
                "after": (chart.day(7), chart.day(8), True),
                "related": (None, None, None),
                "not placed": (None, None, None),
            },
            [("earlier", "after", "end-start")],
        ),
    )

    writes.clear()
    page.mouse.click(*chart.get_entry_point(page, "not placed"))
    page.keyboard.press("Delete")
    check.expect_stays(
        "Delete on a task that is not on the chart does nothing",
        lambda: (chart.read_selected(page), browser.read_writes(page, writes)),
        (["not placed"], []),
    )
    page.mouse.click(*chart.get_entry_point(page, "after"))
    page.keyboard.press("Delete")
    check.expect(
        "Delete on a task selected in the list takes it off too",
        lambda: (
            chart.read_bars(page)["after"],
            chart.read_stored(check.instance, project),
            len(browser.read_writes(page, writes)),
        ),
        (
            (None, None, None),
            (
                {
                    **stored_before[0],
                    "taken off": (None, None, None),
                    "after": (None, None, None),
                },
                [],
            ),
            1,
        ),
    )
    browser.let_page_draw(page)
    page.context.close()
