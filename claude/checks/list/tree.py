"""
The list is a tree: a sub-work item stands under its parent, one level in, where both are in the same group
and the parent is shown. Where the parent is in another group, or a filter hides it, the sub-work item stands
at the top level. A change of parent shows at once, and a folded line stays folded while the list changes.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "parent", "state": "Backlog"},
            {"name": "child", "state": "Backlog", "parent": "parent"},
            {"name": "grandchild", "state": "Backlog", "parent": "child"},
            {"name": "child in todo", "state": "Todo", "parent": "parent"},
            {"name": "alone", "state": "Backlog"},
        ],
    )
    work_items: str = f"/projects/{project.id}/work-items/"
    page: pw.Page = ll.open_list(check, account, project)
    check.expect(
        "every level is unfolded at first; a sub-work item in another group than its parent stands at the "
        "top level of its own",
        lambda: ll.read_lines(page),
        [
            ["Backlog", 0, "parent"],
            ["Backlog", 1, "child"],
            ["Backlog", 2, "grandchild"],
            ["Backlog", 0, "alone"],
            ["Todo", 0, "child in todo"],
        ],
    )

    ins.call_api(
        check.instance,
        "PATCH",
        f"{work_items}{ids['alone']}/",
        {"parent": ids["child"]},
    )
    check.expect(
        "a work item that gets a parent stands under it at once, once",
        lambda: ll.read_lines(page)[:4],
        [
            ["Backlog", 0, "parent"],
            ["Backlog", 1, "child"],
            ["Backlog", 2, "grandchild"],
            ["Backlog", 2, "alone"],
        ],
    )
    ins.call_api(
        check.instance, "PATCH", f"{work_items}{ids['grandchild']}/", {"parent": None}
    )
    check.expect(
        "one that loses its parent stands at the top level at once",
        lambda: sorted(ll.read_lines(page)[:4]),
        sorted(
            [
                ["Backlog", 0, "parent"],
                ["Backlog", 1, "child"],
                ["Backlog", 2, "alone"],
                ["Backlog", 0, "grandchild"],
            ]
        ),
    )

    ll.select_line(page, "parent")
    page.keyboard.press("ArrowLeft")
    check.expect(
        "a folded line hides all that stands under it",
        lambda: sorted(ll.read_titles(page)),
        ["child in todo", "grandchild", "parent"],
    )
    ins.call_api(
        check.instance,
        "POST",
        work_items,
        {
            "name": "late child",
            "state": project.states["Backlog"],
            "parent": ids["parent"],
            "priority": "high",
        },
    )
    ins.call_api(
        check.instance,
        "PATCH",
        f"{work_items}{ids['grandchild']}/",
        {"name": "renamed"},
    )
    check.expect(
        "it stays folded while the list changes: a new sub-work item of it is not shown",
        lambda: sorted(ll.read_titles(page)),
        ["child in todo", "parent", "renamed"],
    )
    page.keyboard.press("ArrowRight")
    check.expect(
        "unfolded, it shows them all",
        lambda: [
            line for line in ll.read_lines(page) if line[0] == "Backlog" and line[1] > 0
        ],
        [
            ["Backlog", 1, "child"],
            ["Backlog", 2, "alone"],
            ["Backlog", 1, "late child"],
        ],
    )

    ll.line(page, "late child").get_by_role("button", name="Priority").click(
        button="right"
    )
    page.get_by_role("menuitem", name="Show only Priority: High").click()
    check.expect(
        "a sub-work item whose parent a filter hides stands at the top level",
        lambda: ll.read_lines(page),
        [["Backlog", 0, "late child"]],
    )
    page.context.close()
