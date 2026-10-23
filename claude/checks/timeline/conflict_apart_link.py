"""
A link whose next task stands later than the link puts it is apart: red, with its text saying by how many days, and
under the pointer its card explains it and offers its ways out; the first, a click, makes the arrow as far as it
stands, stored, and red no more.
"""


import playwright.sync_api as pw

import chart
import instance as ins
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {
                "name": "linking",
                "start_date": chart.day(0),
                "target_date": chart.day(1),
            },
            {"name": "asking", "start_date": chart.day(0), "target_date": chart.day(2)},
            {
                "name": "next",
                "start_date": chart.day(6),
                "target_date": chart.day(6),
                "is_start_fixed": False,
            },
        ],
        [("linking", "next", "end-start", None), ("asking", "next", "end-start", 3)],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=2)
    check.expect(
        "a link whose next task another arrow holds four days later is apart: red, and its text says by how many days",
        lambda: (
            chart.read_texts(page).get(("linking", "next")),
            chart.read_text_looks(page).get(("linking", "next"), (None,))[0],
            chart.read_arrow_looks(page)[("linking", "next")][0],
        ),
        ("linked 4 d apart", True, "danger"),
    )
    chart.hover_arrow(page, "linking", "next", 0.4)
    check.expect(
        "under the pointer its card explains it and offers its ways out",
        lambda: chart.read_card(page),
        [
            "next is linked to linking, but stands 4 days later than the link puts it: the arrow from asking asks for "
            "that.",
            ["Make this arrow in ≥ 4 d", "Remove this arrow"],
        ],
    )
    page.locator(chart.CARD).get_by_role(
        "button", name="Make this arrow in ≥ 4 d"
    ).click()
    check.expect(
        "a click on the first: the arrow is in ≥ 4 d, stored, and it is red no more",
        lambda: (
            chart.read_stored(check.instance, project)[1],
            chart.read_arrow_looks(page)[("linking", "next")][0] == "danger",
        ),
        (
            [("asking", "next", "end-start", 3), ("linking", "next", "end-start", 4)],
            False,
        ),
    )
    page.context.close()
