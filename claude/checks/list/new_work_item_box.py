"""
When the dialog of a new work item is saved, a box goes from the dialog's place to the new line: it starts
exactly where the dialog was and comes to rest exactly on the line, also where the list had to scroll far to
show the line. Then the box is gone, the line is shown and tinted, and nothing of the box stays on the page.
No view transition of the browser is used: in the owner's Chrome such a transition never ends.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# the check reads every frame the page draws, so it has the machine to itself
ALONE: bool = True


def save_and_record(
    page: pw.Page, title: str, state: t.Optional[str]
) -> t.List[ll.Frame]:
    """Makes a work item through the dialog, saved with Ctrl+Enter, and gives the frames from the save on."""
    dialog: pw.Locator = ll.open_create_dialog(page)
    page.keyboard.type(title)
    if state is not None:
        ll.choose_option(page, dialog.locator('button[aria-label^="State, "]'), state)
    ll.record_box(page, title)
    page.keyboard.press("Control+Enter")
    return ll.read_box_frames(page)


def check_box(check: steps.Check, where: str, frames: t.List[ll.Frame]) -> None:
    with_dialog: t.List[ll.Frame] = [frame for frame in frames if frame["dialog"]]
    with_box: t.List[ll.Frame] = [frame for frame in frames if frame["box"]]
    after: ll.Frame = frames[-1]
    check.expect_at_most(
        f"{where}: the box starts where the dialog was (pixels apart)",
        ll.get_distance(with_box[0]["box"], with_dialog[-1]["dialog"]),
        0.5,
    )
    check.expect_at_most(
        f"{where}: it comes to rest on the line (pixels apart)",
        ll.get_distance(with_box[-1]["sentTo"], after["line"]),
        0.5,
    )
    # The line's place is hidden for the time the box takes, and the browser runs the two by itself: they end
    # within a few frames of each other, when the box is less than a pixel from its place.
    check.expect(
        f"{where}: the line is not shown while the box is a pixel or more away from it (box, line)",
        lambda: [
            (frame["box"], frame["line"])
            for frame in with_box
            if frame["shown"] == 1 and ll.get_distance(frame["box"], frame["line"]) >= 1
        ],
        [],
        timeout=0,
    )
    check.expect(
        f"{where}: then the box is gone, and the line is shown, tinted and wholly in view",
        lambda: (after["box"], after["shown"], after["tinted"], after["inView"]),
        (None, 1, True, True),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [{"name": f"backlog {number}", "state": "Backlog"} for number in range(4)]
        + [
            {"name": f"cancelled {number}", "state": "Cancelled"}
            for number in range(30)
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    list_view: pw.Locator = page.locator(".vertical-scrollbar.scrollbar-lg")

    check_box(check, "a line in view", save_and_record(page, "new in view", None))
    check_box(
        check,
        "a line at the far end of the list",
        save_and_record(page, "new at the end", "Cancelled"),
    )
    check.expect_at_least(
        "the list scrolled to that line (pixels)",
        list_view.evaluate("(list) => list.scrollTop"),
        500,
    )
    check_box(
        check,
        "a line far back at the top",
        save_and_record(page, "new at the top", "Backlog"),
    )
    check.expect_at_most(
        "the list scrolled back to that line (pixels)",
        list_view.evaluate("(list) => list.scrollTop"),
        100,
    )
    check.expect(
        "nothing of a box is left on the page, and no view transition of the browser was started",
        lambda: ll.read_left_of_box(page),
        [0, 0, 0, 0],
    )
    check.expect(
        "the three work items are stored in the states chosen for them",
        lambda: {
            name: item["state"]
            for name, item in ins.read_work_items(check.instance, project).items()
            if name.startswith("new ")
        },
        {
            "new in view": project.states["Backlog"],
            "new at the end": project.states["Cancelled"],
            "new at the top": project.states["Backlog"],
        },
    )
    page.context.close()
