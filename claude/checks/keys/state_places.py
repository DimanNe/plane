"""
S and the letter of a state act on the work item that the keys act on wherever it is: the work item in the view
beside the list, on the board with that view open, on the page of one work item (where S opens the palette's page of
states), and on the selected line of the timeline. On the board with nothing open they do nothing. In a project
that names its states otherwise, a letter takes the first state of its state's group.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import list_layout as ll
import page_changes
import steps

PALETTE: str = "[cmdk-input]:not(.menu-choice-picture [cmdk-input])"


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {
                "name": "in the view",
                "start_date": chart.day(0),
                "target_date": chart.day(1),
            },
            {"name": "on the board"},
            {"name": "on its page"},
            {
                "name": "on the timeline",
                "start_date": chart.day(2),
                "target_date": chart.day(3),
            },
        ],
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(page, "in the view")
    page.keyboard.press("Enter")
    page_changes.wait_until_shown(page.locator(ll.PANEL_TITLE))
    page.keyboard.press("s")
    check.expect(
        "the view beside the list open: S opens its menu of states",
        lambda: page.locator(ll.PROPERTY_MENU).count(),
        1,
    )
    page.keyboard.press("p")
    check.expect(
        "and P sets In Progress",
        lambda: (
            ins.read_state_name(check.instance, project, "in the view"),
            page.locator(ll.PROPERTY_MENU).count(),
        ),
        ("In Progress", 0),
    )
    page.context.close()

    ins.set_display(check.instance, account, project, layout="kanban", group_by="state")
    page = browser.open_page(
        check, account, f"/{check.instance.workspace}/projects/{project.id}/issues/"
    )
    page_changes.wait_until_shown(page.get_by_text("on the board", exact=True).first)
    writes: t.List[str] = browser.record_writes(page)
    page.keyboard.press("s")
    page.keyboard.press("d")
    check.expect_stays(
        "the board with nothing open: S D sends nothing",
        lambda: browser.read_writes(page, writes),
        [],
    )
    page.get_by_text("on the board", exact=True).first.click()
    page_changes.wait_until_shown(page.locator(ll.PANEL_TITLE))
    page.keyboard.press("s")
    page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
    page.keyboard.press("t")
    check.expect(
        "the board with the view of a work item open: S T sets Todo",
        lambda: ins.read_state_name(check.instance, project, "on the board"),
        "Todo",
    )
    page.context.close()

    sequence: int = ins.call_api(
        check.instance,
        "GET",
        f"/projects/{project.id}/work-items/{ids['on its page']}/",
    )["sequence_id"]
    page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/browse/{project.identifier}-{sequence}/",
    )
    page_changes.wait_until_shown(page.get_by_text("on its page", exact=True).first)
    page.locator("body").click(position={"x": 5, "y": 300})
    page.keyboard.press("s")
    check.expect(
        "the page of a work item: S opens the palette's page of states",
        lambda: page.locator(PALETTE).count(),
        1,
    )
    page.keyboard.press("c")
    check.expect(
        "and C sets Cancelled and closes the palette",
        lambda: (
            ins.read_state_name(check.instance, project, "on its page"),
            page.locator(PALETTE).count(),
        ),
        ("Cancelled", 0),
    )
    page.context.close()

    page = chart.open_timeline(check, account, project)
    page.mouse.click(*chart.get_entry_point(page, "on the timeline"))
    page.mouse.move(*chart.find_empty_point(page))
    page.keyboard.press("s")
    check.expect(
        "the timeline, a line selected: S opens the menu of states at that line",
        lambda: chart.line(page, "on the timeline").evaluate(
            """(line, popupSelector) => {
              const popup = document.querySelector(popupSelector);
              const control = line.querySelector('[data-filter-property="state_id"] button');
              return !!popup && Math.abs(popup.getBoundingClientRect().left - control.getBoundingClientRect().left) <= 3;
            }""",
            ll.PROPERTY_MENU,
        ),
        True,
    )
    page.keyboard.press("d")
    check.expect(
        "and D sets Done",
        lambda: ins.read_state_name(check.instance, project, "on the timeline"),
        "Done",
    )
    page.context.close()

    other: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.call_api(
        check.instance,
        "PATCH",
        f"/projects/{other.id}/states/{other.states['Done']}/",
        {"name": "Shipped"},
    )
    other = ins.make_state(check.instance, other, "Shipped too", "completed")
    other = ins.Project(
        other.id,
        other.identifier,
        other.name,
        {
            ("Shipped" if name == "Done" else name): state_id
            for name, state_id in other.states.items()
        },
    )
    ins.make_work_items(check.instance, other, [{"name": "named otherwise"}])
    page = ll.open_list(check, account, other, group_by=None)
    ll.select_line(page, "named otherwise")
    page.keyboard.press("s")
    page_changes.wait_until_shown(page.locator(ll.PROPERTY_MENU))
    page.keyboard.press("d")
    check.expect(
        "a project without a state Done: D takes the first state of the group of done states",
        lambda: ins.read_state_name(check.instance, other, "named otherwise"),
        "Shipped",
    )
    page.context.close()
