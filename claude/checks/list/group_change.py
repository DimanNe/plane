"""
A line that goes to another group by a change of its work item is seen going there: a box with the line's
picture starts where the line was and comes to rest where the line is now, or goes out at the edge of the list
or at the header of a folded group when the new place is not shown. The list does not scroll, nothing of the
box stays, and a line that is dragged to another group gets no box.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# the check reads every frame the page draws, so it has the machine to itself
ALONE: bool = True
STATE_AT_LINE: str = 'button[aria-label^="State, "]'
STATE_IN_VIEW_BESIDE: str = '#full-screen-portal button[aria-label^="State, "]'


def get_rect(locator: pw.Locator) -> t.List[float]:
    box: t.Optional[pw.FloatRect] = locator.bounding_box()
    assert box is not None
    return [box["x"], box["y"], box["width"], box["height"]]


def check_box_starts_at_line(
    check: steps.Check, way: str, frames: t.List[ll.Frame], old_place: t.List[float]
) -> None:
    with_box: t.List[ll.Frame] = [frame for frame in frames if frame["box"]]
    check.expect_at_most(
        f"{way}: a box starts where the line was (pixels apart)",
        ll.get_distance(with_box[0]["box"], old_place),
        1,
    )
    check.expect(
        f"{way}: nothing scrolls: the list and a line the change does not concern stay where they are, in every frame",
        lambda: len({(frame["scrolled"], frame["still"]) for frame in frames}),
        1,
        timeout=0,
    )
    check.expect(
        f"{way}: the box never leaves the part of the window the list shows (boxes outside it)",
        lambda: [
            frame["box"]
            for frame in with_box
            if frame["box"][1] < frame["view"][0] - 1
            or frame["box"][1] + frame["box"][3] > frame["view"][1] + 1
        ],
        [],
        timeout=0,
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    # so many in progress that the groups after them are below what the window shows
    ins.make_work_items(
        check.instance,
        project,
        [{"name": f"backlog {number}", "state": "Backlog"} for number in range(4)]
        + [{"name": f"todo {number}", "state": "Todo"} for number in range(3)]
        + [
            {"name": f"in progress {number}", "state": "In Progress"}
            for number in range(30)
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)

    ll.select_line(page, "backlog 1")
    old_place: t.List[float] = get_rect(ll.line(page, "backlog 1"))
    ll.record_box(page, "backlog 1", still="backlog 0")
    page.keyboard.press("s")
    page.keyboard.press("t")
    frames: t.List[ll.Frame] = ll.read_box_frames(page)
    way: str = "S and T, to a place in view"
    check_box_starts_at_line(check, way, frames, old_place)
    with_box: t.List[ll.Frame] = [frame for frame in frames if frame["box"]]
    after: ll.Frame = frames[-1]
    check.expect_at_most(
        f"{way}: the box comes to rest where the line is now (pixels apart)",
        ll.get_distance(with_box[-1]["sentTo"], after["line"]),
        0.5,
    )
    check.expect(
        f"{way}: the box stays whole, and the line is not shown while the box is a pixel or more away",
        lambda: [
            (frame["goesOut"], frame["box"], frame["line"])
            for frame in with_box
            if frame["goesOut"]
            or (
                frame["shown"] == 1
                and ll.get_distance(frame["box"], frame["line"]) >= 1
            )
        ],
        [],
        timeout=0,
    )
    check.expect(
        f"{way}: then the box is gone, and the line is shown in its new group, tinted",
        lambda: (after["box"], after["shown"], after["group"], after["tinted"]),
        (None, 1, "Todo", True),
        timeout=0,
    )
    check.expect(
        f"{way}: the state is stored, and the selection is on the line that took the place",
        lambda: (
            ins.read_state_name(check.instance, project, "backlog 1"),
            ll.read_selected(page),
        ),
        ("Todo", ["backlog 2"]),
    )

    old_place = get_rect(ll.line(page, "todo 0"))
    ll.record_box(page, "todo 0", still="backlog 0")
    ll.line(page, "todo 0").locator(STATE_AT_LINE).click()
    page.get_by_role("option").filter(has_text="Done").click()
    frames = ll.read_box_frames(page, is_line_drawn=False)
    way = "the menu of states at the line, to a place below the view"
    check_box_starts_at_line(check, way, frames, old_place)
    with_box = [frame for frame in frames if frame["box"]]
    check.expect_at_most(
        f"{way}: the box goes down to the lower edge of what the list shows (pixels apart)",
        round(
            abs(
                with_box[-1]["sentTo"][1]
                + with_box[-1]["sentTo"][3]
                - with_box[-1]["view"][1]
            ),
            2,
        ),
        1.5,
    )
    check.expect(
        f"{way}: and is set to go out as it arrives",
        lambda: with_box[-1]["goesOut"],
        True,
        timeout=0,
    )
    check.expect(
        f"{way}: the state is stored, and the selection stays where it was",
        lambda: (
            ins.read_state_name(check.instance, project, "todo 0"),
            ll.read_selected(page),
        ),
        ("Done", ["backlog 2"]),
    )

    header: pw.Locator = ll.group_header(page, "In Progress")
    header.get_by_text("In Progress", exact=True).click()
    check.expect(
        "a click on the name of a group folds it",
        lambda: [group for group in ll.read_groups(page) if group[0] == "In Progress"],
        [["In Progress", 30, 0, True]],
    )
    ll.select_line(page, "todo 1")
    page.keyboard.press("Enter")
    page.locator(STATE_IN_VIEW_BESIDE).wait_for()
    old_place = get_rect(ll.line(page, "todo 1"))
    ll.record_box(page, "todo 1", still="backlog 0")
    page.locator(STATE_IN_VIEW_BESIDE).click()
    page.get_by_role("option").filter(has_text="In Progress").click()
    frames = ll.read_box_frames(page, is_line_drawn=False)
    way = "the state chosen in the view beside the list, to a folded group"
    check_box_starts_at_line(check, way, frames, old_place)
    with_box = [frame for frame in frames if frame["box"]]
    check.expect_at_most(
        f"{way}: the box goes to the header of that group (pixels apart)",
        ll.get_distance(with_box[-1]["sentTo"], get_rect(header)),
        1.5,
    )
    check.expect(
        f"{way}: and is set to go out as it arrives",
        lambda: with_box[-1]["goesOut"],
        True,
        timeout=0,
    )
    check.expect(
        f"{way}: the state is stored, and the folded group counts the work item",
        lambda: (
            ins.read_state_name(check.instance, project, "todo 1"),
            [group for group in ll.read_groups(page) if group[0] == "In Progress"],
        ),
        ("In Progress", [["In Progress", 31, 0, True]]),
    )
    page.keyboard.press("Escape")

    ll.record_box(page, "backlog 3", still="backlog 0")
    ll.carry_line(page, "backlog 3")
    ll.hold_over(page, ll.group_header(page, "Todo"), down=0.5)
    page.mouse.up()
    check.expect(
        "a line dragged to another group is stored there and shown there",
        lambda: (
            ins.read_state_name(check.instance, project, "backlog 3"),
            ["Todo", 0, "backlog 3"] in ll.read_lines(page),
        ),
        ("Todo", True),
    )
    check.expect(
        "and no box was put on the page for it",
        lambda: [frame["box"] for frame in ll.stop_recording_box(page) if frame["box"]],
        [],
        timeout=0,
    )
    check.expect(
        "nothing of a box is left on the page, and no view transition of the browser was started",
        lambda: ll.read_left_of_box(page),
        [0, 0, 0, 0],
    )
    page.context.close()
