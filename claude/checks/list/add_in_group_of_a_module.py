"""
In the list of a module, a work item made by the "+" in the header of a group or by N I goes into that module too.
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
    module: str = ins.call_api(
        check.instance, "POST", f"/projects/{project.id}/modules/", {"name": "a module"}
    )["id"]
    ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/modules/{module}/module-issues/",
        {"issues": [ids["in todo"]]},
    )
    ins.set_display(
        check.instance,
        account,
        project,
        of_list=f"modules/{module}/",
        layout="list",
        group_by="state",
        show_empty_groups=True,
    )
    page: pw.Page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/projects/{project.id}/modules/{module}/",
    )
    ag.check_list_of_cycle_or_module(
        check,
        page,
        "the module",
        f"/projects/{project.id}/modules/{module}/module-issues/",
    )
    page.context.close()
