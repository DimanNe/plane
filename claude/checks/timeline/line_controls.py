"""
Every line of the timeline's list shows, between the work item's id and its name, the state and then the priority of
its work item, as a line of the List layout does, also when the task is not on the chart. A click on either opens
its menu, and what is chosen there is stored and shown at once, the bar taking the colour of the new state. Such a
click selects no line and opens nothing, and a press on either carries nothing onto the chart. A guest sees both and
cannot open them.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import list_layout as ll
import steps

# Of every line from top to bottom: whether the state and the priority stand between its id and its name, in that
# order, what they show, and whether they are disabled.
CONTROLS_JS: str = chart.make_js(
    """
  return lines().map((line) => {
    const entry = line.firstElementChild;
    const state = entry.querySelector('[data-filter-property="state_id"]');
    const priority = entry.querySelector('[data-filter-property="priority"]');
    const left = (element) => element.getBoundingClientRect().left;
    const id = entry.firstElementChild;
    const name = entry.querySelector('span.truncate');
    return [nameOf(line), !!state && !!priority && left(id) < left(state) && left(state) < left(priority) && left(priority) < left(name),
      state?.getAttribute('data-filter-value') ?? null, priority?.getAttribute('data-filter-value') ?? null,
      [state?.querySelector('button').disabled ?? null, priority?.querySelector('button').disabled ?? null]];
  });"""
)


def read_controls(page: pw.Page) -> t.Dict[str, t.List[t.Any]]:
    """By task, as CONTROLS_JS reads them. Work items in different states have no manual order between them."""
    return {values[0]: values[1:] for values in page.evaluate(CONTROLS_JS)}


def control(page: pw.Page, name: str, kind: str) -> pw.Locator:
    return chart.line(page, name).locator(f'[data-filter-property="{kind}"] button')


def read_bar_colour(page: pw.Page, name: str) -> str:
    return (
        chart.bar(page, name)
        .locator("a")
        .evaluate("(link) => getComputedStyle(link).backgroundColor")
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    guest: ins.Account = check.account(ins.ROLE_GUEST)
    project: ins.Project = check.project(
        {account: ins.ROLE_ADMIN, guest: ins.ROLE_GUEST}, guest_view_all_features=True
    )
    states: t.Dict[str, str] = {
        state_id: name for name, state_id in project.states.items()
    }
    chart.make_plan(
        check.instance,
        project,
        [
            {
                "name": "placed",
                "start_date": chart.day(1),
                "target_date": chart.day(3),
                "state": "Todo",
            },
            {"name": "not placed", "state": "Backlog", "priority": "low"},
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project)
    check.expect(
        "every line shows the state and then the priority between the id and the name, with its work item's values, "
        "a line without a bar too",
        lambda: read_controls(page),
        {
            "placed": [True, project.states["Todo"], "none", [False, False]],
            "not placed": [True, project.states["Backlog"], "low", [False, False]],
        },
    )
    writes: t.List[str] = browser.record_writes(page)
    colour: str = read_bar_colour(page, "placed")

    control(page, "placed", "state_id").click()
    page.locator(ll.PROPERTY_MENU).get_by_role("option").filter(has_text="Done").click()
    check.expect(
        "a click on the state opens the menu of states, and Done chosen there is stored and shown at once, the bar "
        "in another colour",
        lambda: (
            states[ins.read_work_items(check.instance, project)["placed"]["state"]],
            read_controls(page)["placed"][1],
            read_bar_colour(page, "placed") != colour,
        ),
        ("Done", project.states["Done"], True),
    )
    control(page, "not placed", "priority").click()
    page.locator(ll.PROPERTY_MENU).get_by_role("option").filter(
        has_text="Urgent"
    ).click()
    check.expect(
        "a click on the priority of a line without a bar opens its menu, and Urgent chosen there is stored and shown",
        lambda: (
            ins.read_work_items(check.instance, project)["not placed"]["priority"],
            read_controls(page)["not placed"][2],
        ),
        ("urgent", "urgent"),
    )
    check.expect(
        "the clicks selected no line, opened no work item, and stored nothing but the two choices",
        lambda: (
            chart.read_selected(page),
            page.locator(
                '#full-screen-portal textarea[placeholder="Work item title"]'
            ).count(),
            len(browser.read_writes(page, writes)),
            chart.read_bars(page),
        ),
        (
            [],
            0,
            2,
            {
                "placed": (chart.day(1), chart.day(3), True),
                "not placed": (None, None, None),
            },
        ),
    )
    box: t.Optional[pw.FloatRect] = control(
        page, "not placed", "state_id"
    ).bounding_box()
    assert box is not None
    chart.drag(
        page,
        (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2),
        (chart.get_day_x(page, chart.day(5), 0.5), box["y"] + box["height"] / 2),
    )
    chart.let_go(page)
    # the rule is that nothing comes, so the step gives the page the time to do it
    check.expect_stays(
        "a press on the state dragged onto the chart carries nothing, selects nothing and opens no menu",
        lambda: (
            chart.read_bars(page)["not placed"],
            chart.read_selected(page),
            page.locator(ll.PROPERTY_MENU).count(),
            len(browser.read_writes(page, writes)),
        ),
        ((None, None, None), [], 0, 2),
        seconds=1,
    )
    page.context.close()

    page = chart.open_timeline(check, guest, project)
    check.expect(
        "a guest sees the state and the priority of every line, disabled",
        lambda: {
            name: [values[0], values[3]] for name, values in read_controls(page).items()
        },
        {"placed": [True, [True, True]], "not placed": [True, [True, True]]},
    )
    control(page, "placed", "state_id").click(force=True)
    control(page, "placed", "priority").click(force=True)
    check.expect_stays(
        "and a click on either opens nothing",
        lambda: page.locator(ll.PROPERTY_MENU).count(),
        0,
        seconds=1,
    )
    page.context.close()
