"""
The address in the browser says which project, which layout and which work item the page shows, and the page
shows what its address says: after a reload, with Back and Forward, typed by hand, in another session.
Selecting and opening a work item changes the address without an entry in the history; a change of layout is
one entry.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

Shown: t.TypeAlias = t.Tuple[str, t.Optional[str], t.List[str], t.Optional[str]]
LAYOUT_JS: str = """
() => [...document.querySelectorAll('button[aria-label$=" Layout"]')]
  .find((button) => button.className.includes('bg-layer-transparent-active'))
  ?.getAttribute('aria-label').replace(' Layout', '') ?? null
"""


def read_page(page: pw.Page) -> Shown:
    """The address, the layout, the selected lines of the list, the title in the view of one work item."""
    return (
        page.evaluate("location.pathname"),
        page.evaluate(LAYOUT_JS),
        ll.read_selected(page),
        ll.read_panel(page),
    )


def choose_layout(page: pw.Page, layout: str) -> None:
    page.get_by_role("button", name=f"{layout} Layout").click()


def read_main_text(page: pw.Page) -> str:
    return page.locator("main").last.inner_text()


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
        layout="list",
        group_by="state",
        order_by="sort_order",
    )
    workspace: str = f"/{check.instance.workspace}"
    home: str = f"{workspace}/{project.identifier.lower()}"

    page: pw.Page = browser.open_page(check, account, f"{workspace}/")
    sidebar: pw.Locator = page.get_by_role("complementary", name="Main sidebar")
    sidebar.get_by_text(project.name, exact=True).click()
    sidebar.locator(f'a[href$="/projects/{project.id}/issues/"]').click()
    check.expect(
        "the project opened from the sidebar has an address made of its identifier",
        lambda: read_page(page),
        (f"{home}/", "List", [], None),
    )
    entries: int = page.evaluate("history.length")
    ll.select_line(page, "item 03")
    check.expect(
        "a selected line puts the work item's number into the address",
        lambda: read_page(page),
        (f"{home}-3/", "List", ["item 03"], None),
    )
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    check.expect(
        "the address follows the arrow keys, and stays when Enter opens the view beside the list",
        lambda: read_page(page),
        (f"{home}-4/", "List", ["item 04"], "item 04"),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes the view; the line stays selected and the address stays",
        lambda: (read_page(page), page.evaluate("history.length")),
        ((f"{home}-4/", "List", ["item 04"], None), entries),
    )
    choose_layout(page, "Board")
    check.expect(
        "the board has an address of its own",
        lambda: read_page(page),
        (f"{home}/board/", "Board", [], None),
    )
    choose_layout(page, "Timeline")
    check.expect(
        "so has the timeline, and each change of layout is one entry in the history",
        lambda: (read_page(page), page.evaluate("history.length")),
        ((f"{home}/timeline/", "Timeline", [], None), entries + 2),
    )
    page.go_back()
    check.expect(
        "Back: the board",
        lambda: read_page(page),
        (f"{home}/board/", "Board", [], None),
    )
    page.go_back()
    check.expect(
        "Back again: the list with the line selected and its view open, as the address says",
        lambda: read_page(page),
        (f"{home}-4/", "List", ["item 04"], "item 04"),
    )
    page.reload()
    check.expect(
        "a reload shows the same, and adds no entry",
        lambda: (read_page(page), page.evaluate("history.length")),
        ((f"{home}-4/", "List", ["item 04"], "item 04"), entries + 2),
    )
    page.go_forward()
    check.expect(
        "Forward: the board, without a view of one work item",
        lambda: read_page(page),
        (f"{home}/board/", "Board", [], None),
    )
    page.get_by_text("item 02", exact=True).click()
    check.expect(
        "on the board a click on a card opens its view and puts its number into the address",
        lambda: read_page(page),
        (f"{home}-2/", "Board", [], "item 02"),
    )
    page.keyboard.press("Escape")
    check.expect(
        "and Escape gives the board's own address back",
        lambda: read_page(page),
        (f"{home}/board/", "Board", [], None),
    )

    page.goto(f"{check.instance.url}{home}/")
    check.expect(
        "the address of the list, typed, decides the layout",
        lambda: read_page(page)[:2],
        (f"{home}/", "List"),
    )
    page.goto(f"{check.instance.url}{workspace}/{project.identifier}-29")
    check.expect(
        "a work item's address typed in capitals and without the slash at its end: put right, its line "
        "selected in the layout used last, its view open",
        lambda: read_page(page),
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

    other: pw.Page = browser.open_page(check, account, f"{home}/calendar/")
    check.expect(
        "in another session the address of the calendar opens the calendar",
        lambda: read_page(other)[:2],
        (f"{home}/calendar/", "Calendar"),
    )
    other.goto(f"{check.instance.url}{workspace}/projects/{project.id}/issues")
    check.expect(
        "the address the project had before turns into the new one, with the layout used last",
        lambda: read_page(other)[:2],
        (f"{home}/calendar/", "Calendar"),
    )
    other.goto(f"{check.instance.url}{workspace}/browse/{project.identifier}-3/")
    check.expect(
        "the page of one work item keeps its address",
        lambda: (
            other.evaluate("location.pathname"),
            other.get_by_text("item 03").count() > 0,
        ),
        (f"{workspace}/browse/{project.identifier}-3/", True),
    )

    other.goto(f"{check.instance.url}{workspace}/projects/{ins.NO_SUCH_ID}/issues/")
    other.wait_for_load_state("networkidle")
    no_project: str = read_main_text(other)
    other.goto(f"{check.instance.url}{workspace}/nosuch/")
    check.expect(
        "the address of a project that does not exist stays as typed and shows what the app shows for one",
        lambda: (other.evaluate("location.pathname"), read_main_text(other)),
        (f"{workspace}/nosuch/", no_project),
    )
    other.goto(f"{check.instance.url}{home}/nosuch/")
    check.expect(
        "an address with a word after the project that names no layout: the app's page for what cannot be found",
        lambda: "cannot be found" in other.locator("body").inner_text(),
        True,
    )
    other.context.close()
    page.context.close()
