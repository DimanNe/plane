"""
A member gets from Delete on the selected line what the line's menu offers a member: a work item that another made
is refused, by the question and by Shift+Delete with the same message, and stays selected; one the member made is
deleted.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    administrator: ins.Account = check.account()
    member: ins.Account = check.account(ins.ROLE_MEMBER)
    project: ins.Project = check.project(
        {administrator: ins.ROLE_ADMIN, member: ins.ROLE_MEMBER}
    )
    ins.make_work_items(check.instance, project, [{"name": "of another"}])
    ins.call_app(
        check.instance.url,
        member,
        "POST",
        f"/workspaces/{check.instance.workspace}/projects/{project.id}/issues/",
        {"name": "of the member", "state_id": project.states["Backlog"]},
    )
    page: pw.Page = ll.open_list(check, member, project)
    question: pw.Locator = page.locator(ll.QUESTION)

    ll.select_line(page, "of another")
    page.keyboard.press("Delete")
    question.get_by_role("button", name="Delete").click()
    check.expect(
        "a member who did not make the work item is refused by the question, as from the menu",
        lambda: any("permission" in text for text in ll.read_messages(page)),
        True,
    )
    refusal: t.List[str] = ll.read_messages(page)
    ll.close_message(page)
    ll.select_line(page, "of another")
    page.keyboard.press("Shift+Delete")
    check.expect(
        "and by Shift+Delete with the same message",
        lambda: ll.read_messages(page),
        refusal,
    )
    check.expect(
        "the work item stays, and stays selected",
        lambda: (
            ins.read_work_item_names(check.instance, project),
            ll.read_selected(page),
        ),
        (["of another", "of the member"], ["of another"]),
    )
    ll.select_line(page, "of the member")
    page.keyboard.press("Shift+Delete")
    check.expect(
        "a work item the member made is deleted",
        lambda: ins.read_work_item_names(check.instance, project),
        ["of another"],
    )
    page.context.close()
