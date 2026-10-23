"""
An address typed by hand decides what the page shows: the address of the list shows the list whatever layout was
used last, and a work item's address, typed in capitals and without the slash at its end, is put right and shows its
line selected in the layout used last, scrolled to, with its view open.
"""

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps
import work_item_addresses as wa


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [{"name": f"item {number:02}", "state": "Backlog"} for number in range(1, 31)],
    )
    ins.set_display(
        check.instance,
        account,
        project,
        layout="board",
        group_by="state",
        order_by="sort_order",
    )
    workspace: str = f"/{check.instance.workspace}"
    home: str = f"{workspace}/{project.identifier.lower()}"
    # the layout used last is the board, so that the typed address of the list is what decides
    page: pw.Page = browser.open_page(check, account, f"{workspace}/")
    page.goto(f"{check.instance.url}{home}/")
    check.expect(
        "the address of the list, typed, decides the layout",
        lambda: wa.read_page(page)[:2],
        (f"{home}/", "List"),
    )
    page.goto(f"{check.instance.url}{workspace}/{project.identifier}-29")
    check.expect(
        "a work item's address typed in capitals and without the slash at its end: put right, its line "
        "selected in the layout used last, its view open",
        lambda: wa.read_page(page),
        (f"{home}-29/", "List", ["item 29"], "item 29"),
    )
    check.expect(
        "and the list has scrolled to that line, far down",
        lambda: page.evaluate(
            """(line) => {
              const at = line.getBoundingClientRect();
              const view = document.querySelector('.vertical-scrollbar.scrollbar-lg').getBoundingClientRect();
              return at.top >= view.top && at.bottom <= view.bottom + 1;
            }""",
            ll.line(page, "item 29").element_handle(),
        ),
        True,
    )
    page.context.close()
