"""
What a line of the list shows beside its title, and what its parts do: the priority as an icon between the
state and the title, every label as a pill of its own, the start of the description after the title, which
Display can switch off. No tooltip says the title again. A line has no "..." button: a right click opens its
menu, once, whose "Copy link" gives the address of the work item's own page.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import steps

# The parts of a line from left to right, each by the name of its button or by what it is.
PARTS_JS: str = """
(line) => [...line.querySelectorAll('button[aria-label], p, [data-description]')]
  .filter((part) => part.getClientRects().length > 0 && !part.parentElement.closest('button[aria-label]'))
  .sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left)
  .map((part) => part.tagName === 'P' ? 'title' : (part.getAttribute('aria-label') ?? 'description').split(',')[0])
"""


def make_label(check: steps.Check, project: ins.Project, name: str) -> str:
    return ins.call_api(
        check.instance,
        "POST",
        f"/projects/{project.id}/labels/",
        {"name": name, "color": "#3b82f6"},
    )["id"]


def read_menus(page: pw.Page) -> int:
    return page.get_by_role("menu").count()


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    labels: t.List[str] = [
        make_label(check, project, name) for name in ("bug", "backend")
    ]
    ins.make_work_items(
        check.instance,
        project,
        [
            {
                "name": "full",
                "state": "Backlog",
                "priority": "high",
                "labels": labels,
                "description_html": "<p>Starts with these words &amp; goes on</p>",
            },
            {"name": "plain", "state": "Backlog"},
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    full: pw.Locator = ll.line(page, "full")

    check.expect(
        "a line shows, from the left: the state, the priority, the title, and after them its other values",
        lambda: full.evaluate(PARTS_JS)[:3],
        ["State", "Priority", "title"],
    )
    check.expect(
        "the priority is named on its icon, also where there is none, and stands nowhere else on the line",
        lambda: (
            [
                button.get_attribute("aria-label")
                for button in full.get_by_role("button", name="Priority").all()
            ],
            ll.line(page, "plain")
            .get_by_role("button", name="Priority")
            .get_attribute("aria-label"),
        ),
        (["Priority, High"], "Priority, None"),
    )
    check.expect(
        "every label has a pill of its own, and no count stands for them",
        lambda: (
            sorted(
                full.get_by_text("bug", exact=True).all_inner_texts()
                + full.get_by_text("backend", exact=True).all_inner_texts()
            ),
            full.get_by_text("2 labels").count(),
        ),
        (["backend", "bug"], 0),
    )
    check.expect(
        "the start of the description stands after the title, as text; a line without one shows none",
        lambda: (
            full.get_by_text("Starts with these words & goes on").count(),
            ll.line(page, "plain").get_by_text("Starts with").count(),
        ),
        (1, 0),
    )

    page.get_by_role("button", name="Display").click()
    page.get_by_text("Description", exact=True).click()
    page.keyboard.press("Escape")
    check.expect(
        "Display has Description, and a click there takes the descriptions off the lines",
        lambda: full.get_by_text("Starts with these words").count(),
        0,
    )
    page.reload()
    check.expect(
        "which is kept for the user: after a reload they are still off",
        lambda: (
            ll.read_titles(page),
            full.get_by_text("Starts with these words").count(),
        ),
        (["full", "plain"], 0),
    )

    full.get_by_role("button", name="Priority").click()
    page.get_by_role("option").filter(has_text="Urgent").click()
    check.expect(
        "a click on the priority's icon opens the priorities, and the one chosen is stored",
        lambda: ins.read_work_items(check.instance, project)["full"]["priority"],
        "urgent",
    )

    tooltip: pw.Locator = page.get_by_role("tooltip")
    full.locator("p").first.hover()
    check.expect_stays(
        "the pointer resting on the title of a line brings no tooltip that says the title again",
        lambda: tooltip.count(),
        0,
    )
    full.get_by_role("button", name="State").hover()
    check.expect(
        "the other tooltips of a line are there: on its state, the state's name",
        lambda: tooltip.filter(has_text="Backlog").count(),
        1,
    )
    full.hover()
    check.expect(
        'a line shows no "..." button, also under the pointer',
        lambda: full.locator('button[aria-haspopup="menu"]')
        .locator("visible=true")
        .count(),
        0,
    )
    ll.select_line(page, "plain")
    full.locator("p").first.click(button="right")
    check.expect(
        "a right click on a line opens one menu, and neither selects nor opens the line",
        lambda: (read_menus(page), ll.read_selected(page), ll.read_panel(page)),
        (1, ["plain"], None),
    )
    ll.line(page, "plain").click(button="right", position={"x": 6, "y": 10}, force=True)
    check.expect(
        "a right click on another line while it is open: never two menus",
        lambda: read_menus(page) <= 1,
        True,
    )
    page.keyboard.press("Escape")
    check.expect("one Escape closes what is open", lambda: read_menus(page), 0)

    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"], origin=check.instance.url
    )
    full.locator("p").first.click(button="right")
    page.get_by_role("menuitem", name="Copy link").click()
    check.expect(
        '"Copy link" in the menu of a line puts the address of the work item\'s own page in the clipboard',
        lambda: page.evaluate("navigator.clipboard.readText()"),
        f"{check.instance.url}/{check.instance.workspace}/browse/{project.identifier}-1/",
    )
    page.context.close()
