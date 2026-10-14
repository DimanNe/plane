"""
The sections of the sidebar can be put in another order: by their heading, or by a handle for the section
that has none. While a section is dragged a line shows where it will land. The order is kept for the user on
the server: it is the same after a reload and in another session.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

SECTION: str = '[aria-label="Main sidebar"] [class~="group/sidebar-section"]'
NO_HEADING: str = "(no heading)"
# The sections from top to bottom, by their heading.
SECTIONS_JS: str = """
([selector, noHeading]) => [...document.querySelectorAll(selector)]
  .map((section) => section.querySelector('button[aria-expanded]')?.innerText.trim() ?? noHeading)
"""
# The lines that show where a dragged section will land: the section they belong to, and its edge.
LANDING_LINES_JS: str = """
([selector, noHeading]) => [...document.querySelectorAll(selector)].flatMap((section) =>
  [...section.children].filter((child) => child.className.includes('h-[2px]')).map((line) => [
    section.querySelector('button[aria-expanded]')?.innerText.trim() ?? noHeading,
    line.className.includes('-top-') ? 'upper' : 'lower',
  ]))
"""


def read_sections(page: pw.Page) -> t.List[str]:
    return page.evaluate(SECTIONS_JS, [SECTION, NO_HEADING])


def read_landing_lines(page: pw.Page) -> t.List[t.List[str]]:
    return page.evaluate(LANDING_LINES_JS, [SECTION, NO_HEADING])


def read_stored_sections(check: steps.Check, account: ins.Account) -> t.List[str]:
    """The sections in the order the server keeps for the account, but for the one of favourites, which the
    sidebar shows only when there are some."""
    stored: ins.JSONObject = ins.call_app(
        check.instance.url,
        account,
        "GET",
        f"/workspaces/{check.instance.workspace}/sidebar-preferences/",
    )
    places: t.Dict[str, float] = {
        key.removeprefix("section_"): value["sort_order"]
        for key, value in stored.items()
        if key.startswith("section_") and key != "section_favorites"
    }
    return sorted(places, key=lambda name: places[name])


def section(page: pw.Page, name: str) -> pw.Locator:
    sections: pw.Locator = page.locator(SECTION)
    heading: pw.Locator = page.locator("button[aria-expanded]")
    if name == NO_HEADING:
        return sections.filter(has_not=heading)
    return sections.filter(has=heading.filter(has_text=name))


def carry_section(page: pw.Page, name: str, over: str, down: float) -> None:
    """Takes a section by its heading, or by its handle when it has none, and holds it over another."""
    if name == NO_HEADING:
        section(page, name).hover()
        grip: pw.Locator = section(page, name).get_by_role(
            "button", name="Drag to rearrange"
        )
    else:
        grip = section(page, name).locator("button[aria-expanded]").first
    browser.press_and_carry(page, browser.get_point(grip, across=0.3))
    browser.carry_to(
        page, browser.get_point(section(page, over), across=0.3, down=down)
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "one"}])
    page: pw.Page = ll.open_list(check, account, project)
    check.expect(
        "the sections stand in their first order",
        lambda: read_sections(page),
        [NO_HEADING, "Workspace", "Projects"],
    )

    carry_section(page, "Projects", over=NO_HEADING, down=0.1)
    check.expect(
        "a section held over the upper part of another: one line shows that it will land above it",
        lambda: read_landing_lines(page),
        [[NO_HEADING, "upper"]],
    )
    page.mouse.up()
    check.expect(
        "dropped, it stands there, and the server keeps the order",
        lambda: (read_sections(page), read_stored_sections(check, account)),
        (
            ["Projects", NO_HEADING, "Workspace"],
            ["projects", "personal", "workspace"],
        ),
    )
    page.reload()
    check.expect(
        "after a reload the order is the same",
        lambda: read_sections(page),
        ["Projects", NO_HEADING, "Workspace"],
    )
    other: pw.Page = ll.open_list(check, account, project)
    check.expect(
        "another session of the user shows the same order",
        lambda: read_sections(other),
        ["Projects", NO_HEADING, "Workspace"],
    )
    other.context.close()

    handle: pw.Locator = section(page, NO_HEADING).get_by_role(
        "button", name="Drag to rearrange"
    )
    section(page, NO_HEADING).hover()
    check.expect(
        "the section without a heading shows a handle while the pointer is over it",
        lambda: handle.evaluate("(handle) => getComputedStyle(handle).opacity"),
        "1",
    )
    ll.line(page, "one").hover()
    check.expect(
        "and hides it when the pointer has left",
        lambda: handle.evaluate("(handle) => getComputedStyle(handle).opacity"),
        "0",
    )
    carry_section(page, NO_HEADING, over="Workspace", down=0.9)
    check.expect(
        "held by that handle over the lower part of the last section: the line shows that it will land under it",
        lambda: read_landing_lines(page),
        [["Workspace", "lower"]],
    )
    page.mouse.up()
    check.expect(
        "dropped, it stands last, and the server keeps the order",
        lambda: (read_sections(page), read_stored_sections(check, account)),
        (
            ["Projects", "Workspace", NO_HEADING],
            ["projects", "workspace", "personal"],
        ),
    )

    heading: pw.Locator = (
        section(page, "Workspace").locator("button[aria-expanded]").first
    )
    heading.click()
    check.expect(
        "a click on a heading folds its section and moves nothing",
        lambda: (heading.get_attribute("aria-expanded"), read_sections(page)),
        ("false", ["Projects", "Workspace", NO_HEADING]),
    )
    page.context.close()
