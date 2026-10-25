"""
The timeline of a cycle's work items and that of a module's are the same timeline: their work items are its lines,
a bar dragged two days later is stored there, and a task without dates carried onto the chart from the list is put
on the day under the pointer.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import page_changes
import steps


def open_place(
    check: steps.Check,
    account: ins.Account,
    project: ins.Project,
    kind: str,
    place_id: str,
) -> pw.Page:
    """The Timeline layout of a cycle or a module, with the panel of its details closed."""
    path: str = f"/workspaces/{check.instance.workspace}/projects/{project.id}/{kind}/{place_id}/user-properties/"
    kept: ins.JSONObject = ins.call_app(check.instance.url, account, "GET", path)
    ins.call_app(
        check.instance.url,
        account,
        "PATCH",
        path,
        {
            "display_filters": {
                **kept["display_filters"],
                "layout": "gantt_chart",
                "order_by": "sort_order",
                "sub_issue": True,
                "show_only_leaves": False,
            },
            "rich_filters": {},
        },
    )
    page: pw.Page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/projects/{project.id}/{kind}/{place_id}/",
    )
    page_changes.wait_until_shown(page.locator(chart.LINE).first)
    page_changes.wait_until_shown(
        page.locator(".vertical-scrollbar.isolate div.top-7").first
    )
    details: pw.Locator = page.locator(
        ".vertical-scrollbar.absolute.right-0 button"
    ).first
    if details.count():
        details.click()
    return page


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project(
        {account: ins.ROLE_ADMIN}, cycle_view=True, module_view=True
    )
    ids: t.Dict[str, str] = chart.make_plan(
        check.instance,
        project,
        [
            {
                "name": "in the cycle",
                "start_date": chart.day(1),
                "target_date": chart.day(3),
            },
            {"name": "without dates in the cycle"},
            {
                "name": "in the module",
                "start_date": chart.day(2),
                "target_date": chart.day(4),
            },
            {"name": "without dates in the module"},
            {
                "name": "elsewhere",
                "start_date": chart.day(0),
                "target_date": chart.day(1),
            },
        ],
    )
    cycle: ins.JSONObject = ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/cycles/",
        {
            "name": "A cycle",
            "start_date": chart.day(-5),
            "end_date": chart.day(20),
            "project_id": project.id,
        },
    )
    ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/cycles/{cycle['id']}/cycle-issues/",
        {"issues": [ids["in the cycle"], ids["without dates in the cycle"]]},
    )
    module: ins.JSONObject = ins.call_api(
        check.instance, "POST", f"/projects/{project.id}/modules/", {"name": "A module"}
    )
    ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/modules/{module['id']}/module-issues/",
        {"issues": [ids["in the module"], ids["without dates in the module"]]},
    )

    kind: str
    place_id: str
    name: str
    offset: int
    for kind, place_id, name, offset in (
        ("cycles", cycle["id"], "cycle", 1),
        ("modules", module["id"], "module", 2),
    ):
        page: pw.Page = open_place(check, account, project, kind, place_id)
        check.expect(
            f"the timeline of a {name}: its work items are the lines",
            lambda: sorted(chart.read_lines(page)),
            sorted([f"in the {name}", f"without dates in the {name}"]),
        )
        chart.drag_bar(page, f"in the {name}", 2)
        chart.let_go(page)
        check.expect(
            "  a bar dragged two days later is stored there",
            lambda: chart.read_stored(check.instance, project)[0][f"in the {name}"],
            (chart.day(offset + 2), chart.day(offset + 4), True),
        )
        chart.carry_entry(page, f"without dates in the {name}")
        page.mouse.move(
            chart.get_day_x(page, chart.day(6), 0.5),
            chart.get_line_y(page, f"without dates in the {name}"),
            steps=8,
        )
        chart.let_go(page)
        check.expect(
            "  a bar dragged two days later is stored there, and a task without dates carried onto the chart is put on "
            "the day under the pointer",
            lambda: chart.read_stored(check.instance, project)[0][
                f"without dates in the {name}"
            ],
            (chart.day(6), chart.day(6), True),
        )
        page.context.close()
