"""
A line of the timeline is moved up or down by its name or by its bar, whose first movement then goes across the
lines; the line goes with the pointer, entry and bar together, and a line marks where it would land. Let go, it lands
before the line it was dropped on and nothing changes its dates; Escape leaves it where it was. The first move in a
list that is in another order puts the list in the manual order with every line where it stood, and stores the
place of every work item whose place changed; the timeline is not drawn anew. Lines that Leaves hides keep their
places among the others.
"""

import typing as t

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps

# the line that the timeline draws where a moved line would land
DROP_LINE_JS: str = chart.make_js(
    """
  const mark = chart.querySelector('div[class~="inset-x-0"][class~="z-[3]"]:not([class~="group/line"])');
  if (!mark) return null;
  const top = mark.getBoundingClientRect().top + 1;
  // the line that is moved is drawn where the pointer holds it, and is not where it would land
  const line = lines().find((other) => !other.style.transform && Math.abs(other.getBoundingClientRect().top - top) <= 2);
  return line ? nameOf(line) : 'the end';"""
)


def read_order_by(
    check: steps.Check, account: ins.Account, project: ins.Project
) -> str:
    """The order of the list that the page has kept on the server for the account."""
    return ins.call_app(
        check.instance.url,
        account,
        "GET",
        f"/workspaces/{check.instance.workspace}/projects/{project.id}/user-properties/",
    )["display_filters"]["order_by"]


def read_manual_order(check: steps.Check, project: ins.Project) -> t.List[str]:
    items: t.Dict[str, ins.JSONObject] = ins.read_work_items(check.instance, project)
    return sorted(items, key=lambda name: items[name]["sort_order"])


def read_places(check: steps.Check, project: ins.Project) -> t.Dict[str, float]:
    return {
        name: item["sort_order"]
        for name, item in ins.read_work_items(check.instance, project).items()
    }


def count_changed_places(
    check: steps.Check, project: ins.Project, places: t.Dict[str, float]
) -> int:
    return len(
        [
            name
            for name, place in read_places(check, project).items()
            if place != places[name]
        ]
    )


def count_patches(page: pw.Page, writes: t.List[str]) -> int:
    """The requests that stored the place of a work item."""
    return len(
        [
            write
            for write in browser.read_writes(page, writes)
            if write.startswith("PATCH") and "/issues/" in write
        ]
    )


def move_before(order: t.Sequence[str], name: str, before: str) -> t.List[str]:
    rest: t.List[str] = [other for other in order if other != name]
    rest.insert(rest.index(before), name)
    return rest


def drag_line(page: pw.Page, start: browser.Point, target: str) -> None:
    """Presses at a point and moves up or down to the top of the line of a task."""
    box: t.Optional[pw.FloatRect] = chart.line(page, target).bounding_box()
    assert box is not None
    chart.drag(page, start, (start[0] + 3, box["y"] + 2))


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "one", "start_date": chart.day(0), "target_date": chart.day(1)},
            {"name": "two", "start_date": chart.day(1), "target_date": chart.day(2)},
            {"name": "three", "start_date": chart.day(2), "target_date": chart.day(3)},
            {"name": "parent", "start_date": chart.day(0), "target_date": chart.day(5)},
            {
                "name": "child a",
                "parent": "parent",
                "start_date": chart.day(3),
                "target_date": chart.day(4),
            },
            {
                "name": "child b",
                "parent": "parent",
                "start_date": chart.day(4),
                "target_date": chart.day(5),
            },
            {"name": "four", "start_date": chart.day(3), "target_date": chart.day(3)},
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project, order_by="-created_at")
    newest_first: t.List[str] = [
        "four",
        "child b",
        "child a",
        "parent",
        "three",
        "two",
        "one",
    ]
    check.expect(
        "the list stands in the order the work items were made, newest first",
        lambda: chart.read_lines(page),
        newest_first,
    )
    page.evaluate(chart.make_js("chart.__kept = true;"))
    writes: t.List[str] = browser.record_writes(page)
    places: t.Dict[str, float] = read_places(check, project)

    entry: browser.Point = chart.get_entry_point(page, "two")
    box: t.Optional[pw.FloatRect] = chart.line(page, "two").bounding_box()
    assert box is not None
    target: t.Optional[pw.FloatRect] = chart.line(page, "parent").bounding_box()
    assert target is not None
    drag_line(page, entry, "parent")
    check.expect(
        "a line held by its name over the top of another goes with the pointer, entry and bar together, a line "
        "marks the top of that other line, and the other lines stay",
        lambda: (
            round(
                chart.line(page, "two").bounding_box()["y"]
                - box["y"]
                - (target["y"] + 2 - entry[1])
            )
            in range(-1, 2),
            page.evaluate(DROP_LINE_JS),
            [name for name in chart.read_lines(page) if name != "two"],
        ),
        (True, "parent", [name for name in newest_first if name != "two"]),
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    # the rule is that nothing comes after Escape, so the step gives the page the time to send it
    check.expect_stays(
        "Escape: the line is back, nothing is sent, and the list is in its order still",
        lambda: (
            chart.read_lines(page),
            browser.read_writes(page, writes),
            read_order_by(check, account, project),
        ),
        (newest_first, [], "-created_at"),
        seconds=1,
    )

    drag_line(page, entry, "parent")
    chart.let_go(page)
    moved: t.List[str] = move_before(newest_first, "two", "parent")
    check.expect(
        "let go: it stands before the line it was dropped on, the list is in the manual order now, and the manual "
        "order stored is the order on the page",
        lambda: (
            chart.read_lines(page),
            read_order_by(check, account, project),
            read_manual_order(check, project),
        ),
        (moved, "sort_order", moved),
    )
    check.expect(
        "a request for each work item whose place changed, the timeline the same one, and no dates changed",
        lambda: (
            count_patches(page, writes)
            == count_changed_places(check, project, places)
            > 0,
            page.evaluate(chart.make_js("return chart.__kept === true;")),
            chart.read_stored(check.instance, project)[0]["two"],
        ),
        (True, True, (chart.day(1), chart.day(2), True)),
    )
    page.reload()
    page.locator(chart.LINE).first.wait_for()
    check.expect(
        "after a reload the lines stand in the same order",
        lambda: chart.read_lines(page),
        moved,
    )

    writes = browser.record_writes(page)
    drag_line(page, chart.get_entry_point(page, "child b"), "three")
    chart.let_go(page)
    again: t.List[str] = move_before(moved, "child b", "three")
    check.expect(
        "a move downwards lands before the line it was dropped on, in one request, and is stored",
        lambda: (
            chart.read_lines(page),
            count_patches(page, writes),
            read_manual_order(check, project),
        ),
        (again, 1, again),
    )
    grab: browser.Point = chart.get_bar_point(page, "one")
    four: t.Optional[pw.FloatRect] = chart.line(page, "four").bounding_box()
    assert four is not None
    chart.drag(page, grab, (grab[0] + 40, four["y"] + 2))
    chart.let_go(page)
    check.expect(
        "a bar whose first movement goes up moves its line, and its dates stay, though the pointer went sideways too",
        lambda: (
            chart.read_lines(page),
            chart.read_stored(check.instance, project)[0]["one"],
        ),
        (move_before(again, "one", "four"), (chart.day(0), chart.day(1), True)),
    )
    page.context.close()

    page = chart.open_timeline(check, account, project, order_by="-created_at")
    everything: t.List[str] = chart.read_lines(page)
    page.get_by_role("button", name="Leaves", exact=True).click()
    leaves: t.List[str] = [name for name in everything if name != "parent"]
    check.expect(
        "Leaves lists every work item but the parent",
        lambda: chart.read_lines(page),
        leaves,
    )
    drag_line(page, chart.get_entry_point(page, "child a"), "four")
    chart.let_go(page)
    check.expect(
        "with only leaves listed, in another order, the first move works the same",
        lambda: (chart.read_lines(page), read_order_by(check, account, project)),
        (move_before(leaves, "child a", "four"), "sort_order"),
    )
    page.get_by_role("button", name="All", exact=True).click()
    check.expect(
        "All: the parent, which was hidden, stands where it stood among the others, and so it is stored",
        lambda: (chart.read_lines(page), read_manual_order(check, project)),
        (move_before(everything, "child a", "four"),) * 2,
    )
    page.context.close()
