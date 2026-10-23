"""
The address in the browser says which project, which layout and which work item the page shows, and the page
shows what its address says after a reload and with Back and Forward. Selecting and opening a work item changes the
address without an entry in the history; a change of layout is one entry.
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
        [{"name": f"item {number:02}", "state": "Backlog"} for number in range(1, 6)],
    )
    ins.set_display(
        check.instance,
        account,
        project,
        layout="list",
        group_by="state",
        order_by="sort_order",
    )
    workspace: str = f"/{check.instance.workspace}"
    home: str = f"{workspace}/{project.identifier.lower()}"

    page: pw.Page = browser.open_page(check, account, f"{workspace}/")
    sidebar: pw.Locator = page.get_by_role("complementary", name="Main sidebar")
    # the project is open in the sidebar, with its pages under it
    sidebar.locator(f'a[href$="/projects/{project.id}/issues/"]').click()
    check.expect(
        "the project opened from the sidebar has an address made of its identifier",
        lambda: wa.read_page(page),
        (f"{home}/", "List", [], None),
    )
    entries: int = page.evaluate("history.length")
    ll.select_line(page, "item 03")
    check.expect(
        "a selected line puts the work item's number into the address",
        lambda: wa.read_page(page),
        (f"{home}-3/", "List", ["item 03"], None),
    )
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    check.expect(
        "the address follows the arrow keys, and stays when Enter opens the view beside the list",
        lambda: wa.read_page(page),
        (f"{home}-4/", "List", ["item 04"], "item 04"),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes the view; the line stays selected and the address stays",
        lambda: (wa.read_page(page), page.evaluate("history.length")),
        ((f"{home}-4/", "List", ["item 04"], None), entries),
    )
    wa.choose_layout(page, "Board")
    check.expect(
        "the board has an address of its own",
        lambda: wa.read_page(page),
        (f"{home}/board/", "Board", [], None),
    )
    wa.choose_layout(page, "Timeline")
    check.expect(
        "so has the timeline, and each change of layout is one entry in the history",
        lambda: (wa.read_page(page), page.evaluate("history.length")),
        ((f"{home}/timeline/", "Timeline", [], None), entries + 2),
    )
    page.go_back()
    check.expect(
        "Back: the board",
        lambda: wa.read_page(page),
        (f"{home}/board/", "Board", [], None),
    )
    page.go_back()
    check.expect(
        "Back again: the list with the line selected and its view open, as the address says",
        lambda: wa.read_page(page),
        (f"{home}-4/", "List", ["item 04"], "item 04"),
    )
    page.reload()
    check.expect(
        "a reload shows the same, and adds no entry",
        lambda: (wa.read_page(page), page.evaluate("history.length")),
        ((f"{home}-4/", "List", ["item 04"], "item 04"), entries + 2),
    )
    page.go_forward()
    check.expect(
        "Forward: the board, without a view of one work item",
        lambda: wa.read_page(page),
        (f"{home}/board/", "Board", [], None),
    )
    page.get_by_text("item 02", exact=True).click()
    check.expect(
        "on the board a click on a card opens its view and puts its number into the address",
        lambda: wa.read_page(page),
        (f"{home}-2/", "Board", [], "item 02"),
    )
    page.keyboard.press("Escape")
    check.expect(
        "and Escape gives the board's own address back",
        lambda: wa.read_page(page),
        (f"{home}/board/", "Board", [], None),
    )
    page.context.close()
