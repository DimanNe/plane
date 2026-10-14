"""
An open list and an open work item follow what others change, without a reload: a change made through
/api/v1/, as an agent makes it, and a change made by another user in a browser. What the user is typing
meanwhile stays, and is stored.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

VIEW_BESIDE: str = "#full-screen-portal"


def change(
    check: steps.Check, project: ins.Project, work_item: str, fields: ins.JSONObject
) -> None:
    """A change of a work item made through /api/v1/."""
    ins.call_api(
        check.instance,
        "PATCH",
        f"/projects/{project.id}/work-items/{work_item}/",
        fields,
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    other: ins.Account = check.account(ins.ROLE_MEMBER)
    project: ins.Project = check.project(
        {account: ins.ROLE_ADMIN, other: ins.ROLE_MEMBER}
    )
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "one", "state": "Backlog"},
            {"name": "two", "state": "Backlog"},
            {"name": "three", "state": "Backlog"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    page.evaluate("window.__same_page = true")

    change(check, project, ids["one"], {"name": "one renamed"})
    check.expect(
        "a name changed through the API shows on the line",
        lambda: ll.read_titles(page),
        ["one renamed", "two", "three"],
    )
    change(check, project, ids["two"], {"state": project.states["Todo"]})
    check.expect(
        "a state changed through the API: the line stands in that group, and its circle names the state",
        lambda: (
            ll.read_lines(page),
            ll.line(page, "two")
            .get_by_role("button", name="State")
            .get_attribute("aria-label"),
        ),
        (
            [
                ["Backlog", 0, "one renamed"],
                ["Backlog", 0, "three"],
                ["Todo", 0, "two"],
            ],
            "State, Todo",
        ),
    )
    change(check, project, ids["three"], {"parent": ids["one"]})
    check.expect(
        "a parent set through the API: the line stands under its parent",
        lambda: ll.read_lines(page),
        [["Backlog", 0, "one renamed"], ["Backlog", 1, "three"], ["Todo", 0, "two"]],
    )
    made: t.Dict[str, str] = ins.make_work_items(
        check.instance, project, [{"name": "made by another", "state": "Todo"}]
    )
    check.expect(
        "a work item made through the API appears",
        lambda: "made by another" in ll.read_titles(page),
        True,
    )
    ins.call_api(
        check.instance,
        "DELETE",
        f"/projects/{project.id}/work-items/{made['made by another']}/",
    )
    check.expect(
        "and goes when it is deleted through the API",
        lambda: "made by another" in ll.read_titles(page),
        False,
    )

    ll.select_line(page, "one renamed")
    page.keyboard.press("Enter")
    view: pw.Locator = page.locator(VIEW_BESIDE)
    description: pw.Locator = view.locator(".ProseMirror[contenteditable='true']").first
    description.click()
    page.keyboard.type("typed by me")
    change(check, project, ids["one"], {"priority": "urgent"})
    check.expect(
        "while the user types a description in the view beside the list, a priority changed through the API "
        "shows there, and what was typed stays",
        lambda: (
            view.get_by_text("Urgent", exact=True).count() > 0,
            description.inner_text().strip(),
        ),
        (True, "typed by me"),
    )
    check.expect(
        "what was typed is stored",
        lambda: "typed by me"
        in ins.read_work_items(check.instance, project)["one renamed"][
            "description_html"
        ],
        True,
    )
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    page_of_other: pw.Page = ll.open_list(check, other, project)
    ll.select_line(page_of_other, "two")
    page_of_other.keyboard.press("s")
    page_of_other.keyboard.press("d")
    check.expect(
        "a state set by another user in a browser: the line stands in that group here too",
        lambda: ["Done", 0, "two"] in ll.read_lines(page),
        True,
    )
    check.expect(
        "the page was not loaded again in all this",
        lambda: page.evaluate("window.__same_page"),
        True,
    )
    page_of_other.context.close()
    page.context.close()
