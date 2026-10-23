"""
An arrow that asks a task fixed on its day to start later than that day is a conflict: it is red, and its text says
in red by how many days the task is too early. Under the pointer a card explains it, with the tasks and the arrows
that produce it ringed in red, and offers the ways out; away from the arrow the card and the rings go.
"""

import playwright.sync_api as pw

import chart
import instance as ins
import steps
import timeline_conflict as tc


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project
    page: pw.Page
    project, page = tc.open_conflict(check, account)
    check.expect(
        "the arrow that asks a fixed task to start later is red, and so is its text, which says by how many days the "
        "task is too early; the other arrow says its days",
        lambda: (
            tc.read_red(page)[0],
            chart.read_texts(page),
            chart.read_text_looks(page)[("middle", "late")][0],
        ),
        (
            [("middle", "late")],
            {("first", "middle"): "in ≥ 1 d", ("middle", "late"): "2 d too early"},
            True,
        ),
    )
    check.expect(
        "no card is shown without the pointer", lambda: chart.read_card(page), None
    )
    chart.hover_arrow(page, "middle", "late", 0.4)
    check.expect(
        "under the pointer the card says which task is fixed on which day and what the arrow asks for and why, and "
        "offers the ways out",
        lambda: chart.read_card(page),
        [
            f"late is fixed on {tc.write_day(5)}. This arrow asks it to start no earlier than {tc.write_day(7)}: 2 days "
            f"after middle ends on {tc.write_day(4)}.",
            [
                "Let it follow its arrows",
                f"Fix it on {tc.write_day(7)}",
                "Shorten the delay to 0 d",
                "Remove this arrow",
            ],
        ],
    )
    check.expect(
        "the tasks and the arrows that produce it, back to a fixed task, are red",
        lambda: tc.read_red(page),
        ([("first", "middle"), ("middle", "late")], ["first", "middle", "late"]),
    )
    page.mouse.move(*chart.find_empty_point(page), steps=4)
    check.expect(
        "away from the arrow the card and the rings go, and the texts stay",
        lambda: (chart.read_card(page), tc.read_red(page), len(chart.read_texts(page))),
        (None, ([("middle", "late")], []), 2),
    )
    page.context.close()
