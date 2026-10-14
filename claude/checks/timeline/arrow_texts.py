"""
Every arrow that a task follows says over itself what it is: "linked", or "in ≥ n d" with its days. An arrow into
a task fixed on its day says nothing over itself; the task shows "on" and its day beside its bar instead. No text
lies on a bar or on another text. While a bar is dragged, the text of the arrow whose days the move changes counts
them.
"""

import playwright.sync_api as pw

import browser
import chart
import instance as ins
import steps

# Whether a text over an arrow or a date beside a bar lies on a bar or on another such text.
OVERLAPS_JS: str = chart.make_js(
    """
  const isOver = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  const texts = [...textLayers()].flatMap((layer) => [...layer.children]).map((text) => text.getBoundingClientRect());
  const bars = lines().map(barOf).filter((bar) => bar).map((bar) => bar.getBoundingClientRect());
  return [
    texts.filter((text) => bars.some((bar) => isOver(text, bar))).length,
    texts.filter((text, index) => texts.some((other, otherIndex) => otherIndex !== index && isOver(text, other))).length,
  ];"""
)


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    chart.make_plan(
        check.instance,
        project,
        [
            {"name": "first", "start_date": chart.day(0), "target_date": chart.day(1)},
            {
                "name": "after",
                "start_date": chart.day(4),
                "target_date": chart.day(5),
                "is_start_fixed": False,
            },
            {"name": "fixed", "start_date": chart.day(8), "target_date": chart.day(9)},
            {
                "name": "linked",
                "start_date": chart.day(10),
                "target_date": chart.day(11),
                "is_start_fixed": False,
            },
            {
                "name": "with",
                "start_date": chart.day(1),
                "target_date": chart.day(2),
                "is_start_fixed": False,
            },
        ],
        [
            ("first", "after", "end-start", 2),
            ("after", "fixed", "end-start", 0),
            ("fixed", "linked", "end-start", None),
            ("first", "with", "start-start", 1),
        ],
    )
    page: pw.Page = chart.open_timeline(check, account, project, arrows=4)
    page.mouse.move(*chart.find_empty_point(page))
    check.expect(
        "every arrow that a task follows says what it is over itself, and the arrow into the fixed task nothing",
        lambda: chart.read_texts(page),
        {
            ("first", "after"): "in ≥ 2 d",
            ("fixed", "linked"): "linked",
            ("first", "with"): "in ≥ 1 d",
        },
    )
    check.expect(
        "the fixed task to which an arrow leads shows on and its day beside its bar, and no other date stands beside "
        "a bar",
        lambda: chart.read_dates_beside(page),
        {"fixed": [f"on {chart.format_day(chart.day(8))}"]},
    )
    check.expect(
        "no text lies on a bar or on another text",
        lambda: page.evaluate(OVERLAPS_JS),
        [0, 0],
    )
    on: browser.Point = browser.get_point(
        page.locator('div[class~="z-[3]"] [data-actionable]')
        .filter(has_text="on")
        .first
    )
    chart.turn_wheel(page, on, 1)
    check.expect(
        "a notch up on that on: the fixed task follows its arrow again, linked, and loses the mark of a fixed start",
        lambda: (
            chart.read_bars(page)["fixed"],
            chart.read_text_at(page, on),
        ),
        ((chart.day(6), chart.day(7), False), "linked"),
    )
    page.keyboard.press("Escape")
    page.mouse.move(*chart.find_empty_point(page))
    check.expect(
        "Escape puts it back on its day",
        lambda: chart.read_bars(page)["fixed"],
        (chart.day(8), chart.day(9), True),
    )
    chart.drag_bar(page, "after", 2)
    check.expect(
        "while the task after the first is dragged two days later, the text of its arrow counts the days",
        lambda: chart.read_texts(page).get(("first", "after")),
        "in ≥ 4 d",
    )
    page.keyboard.press("Escape")
    chart.let_go(page)
    check.expect(
        "after Escape it says its stored days again",
        lambda: chart.read_texts(page).get(("first", "after")),
        "in ≥ 2 d",
    )
    page.context.close()
