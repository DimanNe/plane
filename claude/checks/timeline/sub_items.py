"""
The timeline lists sub-work items whatever the stored "Show sub-work items" says, and its Display menu does not
offer that choice.
"""

import playwright.sync_api as pw

import chart
import instance as ins
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "parent", "start_date": chart.day(0), "target_date": chart.day(4)},
            {
                "name": "child",
                "parent": "parent",
                "start_date": chart.day(1),
                "target_date": chart.day(2),
            },
            {
                "name": "grandchild",
                "parent": "child",
                "start_date": chart.day(2),
                "target_date": chart.day(2),
            },
            {"name": "plain", "start_date": chart.day(3), "target_date": chart.day(5)},
        ],
    )
    is_shown: bool
    for is_shown in (False, True):
        page: pw.Page = chart.open_timeline(check, account, project, sub_issue=is_shown)
        check.expect(
            f'with "Show sub-work items" stored as {is_shown}, the timeline lists the sub-work items',
            lambda: chart.read_lines(page),
            ["parent", "child", "grandchild", "plain"],
        )
        page.get_by_role("button", name="Display").click()
        menu: pw.Locator = (
            page.locator('[role="dialog"], [role="menu"]')
            .filter(has_text="Order by")
            .last
        )
        menu.wait_for()
        check.expect(
            "  and its Display menu offers no choice of sub-work items",
            lambda: "sub-work items" in menu.inner_text().lower(),
            False,
        )
        page.context.close()
