"""
Where the system asks for less motion, nothing is carried across the list: a new work item and a line that
changes its group get no box. The line is pointed out by its tint alone, where it is, and is in view.
"""

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [{"name": f"backlog {number:02}", "state": "Backlog"} for number in range(30)],
    )
    page: pw.Page = ll.open_list(check, account, project)
    page.emulate_media(reduced_motion="reduce")

    ll.record_box(page, "made")
    ll.select_line(page, "backlog 01")
    ll.create_work_item(page, "made")
    check.expect(
        "a new work item: its line is selected, tinted and in view",
        lambda: (
            ll.read_selected(page),
            ll.read_tinted(page),
            page.evaluate(
                """(line) => {
                  const at = line.getBoundingClientRect();
                  const view = document.querySelector('.vertical-scrollbar.scrollbar-lg').getBoundingClientRect();
                  return at.top >= view.top && at.bottom <= view.bottom + 1;
                }""",
                ll.line(page, "made").element_handle(),
            ),
        ),
        (["made"], ["made"], True),
    )
    check.expect(
        "and no box was put on the page for it",
        lambda: [frame["box"] for frame in ll.stop_recording_box(page) if frame["box"]],
        [],
        timeout=0,
    )

    ll.record_box(page, "backlog 02")
    ll.select_line(page, "backlog 02")
    page.keyboard.press("s")
    page.keyboard.press("t")
    check.expect(
        "a line sent to another group by S and T is there, tinted",
        lambda: (
            ["Todo", 0, "backlog 02"] in ll.read_lines(page),
            ll.read_tinted(page),
        ),
        (True, ["backlog 02"]),
    )
    check.expect(
        "and no box was put on the page for it",
        lambda: [frame["box"] for frame in ll.stop_recording_box(page) if frame["box"]],
        [],
        timeout=0,
    )
    page.context.close()
