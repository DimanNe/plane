"""
A line of the list shows the state of its work item as a circle left of the title, and nowhere else. The
circle of a started state is filled by how far that state stands among the started ones of its project. A
click on the circle opens the states to choose from and selects the line, and opens nothing else.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# The part of the circle that is filled: 0 for a ring, None where the state's own picture is drawn instead.
SECTOR_JS: str = """
(button) => {
  const circles = button.querySelectorAll('svg circle');
  if (circles.length < 2) return circles.length ? 0 : null;
  return Math.round(Number(circles[1].getAttribute('stroke-dasharray').split(' ')[0]) * 1000) / 1000;
}
"""


def circle(page: pw.Page, title: str) -> pw.Locator:
    return ll.line(page, title).locator('button[aria-label^="State, "]')


def read_sectors(
    page: pw.Page, titles: t.Sequence[str]
) -> t.Dict[str, t.Optional[float]]:
    return {title: circle(page, title).evaluate(SECTOR_JS) for title in titles}


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "backlog", "state": "Backlog"},
            {"name": "todo", "state": "Todo"},
            {"name": "started", "state": "In Progress"},
            {"name": "done", "state": "Done"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)

    check.expect(
        "the circle of a line is named after the state, and no other part of the line names it",
        lambda: (
            circle(page, "todo").get_attribute("aria-label"),
            ll.line(page, "todo").get_by_text("Todo", exact=True).count(),
        ),
        ("State, Todo", 0),
    )
    check.expect(
        "it stands left of the title",
        lambda: page.evaluate(
            "([circle, title]) => circle.getBoundingClientRect().right <= title.getBoundingClientRect().left",
            [
                circle(page, "todo").element_handle(),
                ll.line(page, "todo").locator("p").first.element_handle(),
            ],
        ),
        True,
    )
    check.expect(
        "with one started state in the project its circle is half filled; a state not started is a ring; "
        "a completed one has its own picture",
        lambda: read_sectors(page, ["backlog", "todo", "started", "done"]),
        {"backlog": 0, "todo": 0, "started": 0.5, "done": None},
    )

    address_of_list: str = page.url
    circle(page, "todo").click()
    check.expect(
        "a click on the circle opens the states of the project to choose from",
        lambda: sorted(page.get_by_role("option").all_inner_texts()),
        sorted(project.states),
    )
    check.expect(
        "the click selects the line, and the address names its work item, as it names every selected one; the "
        "click opens no work item",
        lambda: (page.url, ll.read_selected(page), ll.read_panel(page)),
        (f"{address_of_list.rstrip('/')}-2/", ["todo"], None),
    )
    page.get_by_role("option").filter(has_text="In Progress").click()
    check.expect(
        "the state chosen there is stored, and the circle is named after it",
        lambda: (
            ins.read_work_items(check.instance, project)["todo"]["state"],
            circle(page, "todo").get_attribute("aria-label"),
        ),
        (project.states["In Progress"], "State, In Progress"),
    )
    circle(page, "backlog").focus()
    page.keyboard.press("Enter")
    check.expect(
        "Enter on a circle that has the focus opens the states too",
        lambda: page.get_by_role("option").count(),
        len(project.states),
    )
    page.keyboard.press("Escape")
    check.expect(
        "and Escape closes them", lambda: page.get_by_role("option").count(), 0
    )

    project = ins.make_state(check.instance, project, "In Review", "started")
    ins.make_work_items(
        check.instance, project, [{"name": "in review", "state": "In Review"}]
    )
    page.reload()
    check.expect(
        "with two started states the circle of the first is a third filled and that of the second two thirds",
        lambda: read_sectors(page, ["started", "in review"]),
        {"started": 0.333, "in review": 0.667},
    )
    page.context.close()
