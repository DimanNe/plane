"""
In the list of a cycle, a work item made by the "+" in the header of a group or by N I goes into that cycle too.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_add_in_group as ag
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project(
        {account: ins.ROLE_ADMIN}, cycle_view=True, module_view=True
    )
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "in backlog", "state": "Backlog"},
            {"name": "in todo", "state": "Todo"},
            {"name": "in progress", "state": "In Progress"},
        ],
    )
    cycle: str = ins.call_api(
        check.instance, "POST", f"/projects/{project.id}/cycles/", {"name": "a cycle"}
    )["id"]
    ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/cycles/{cycle}/cycle-issues/",
        {"issues": [ids["in todo"]]},
    )
    ins.set_display(
        check.instance,
        account,
        project,
        of_list=f"cycles/{cycle}/",
        layout="list",
        group_by="state",
        show_empty_groups=True,
    )
    page: pw.Page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/projects/{project.id}/cycles/{cycle}/",
    )
    ag.check_list_of_cycle_or_module(
        check, page, "the cycle", f"/projects/{project.id}/cycles/{cycle}/cycle-issues/"
    )
    page.context.close()
