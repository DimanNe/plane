"""
The sections of the sidebar can be put in another order: by their heading, or by a handle for the section
that has none. While a section is dragged a line shows where it will land. The order is kept for the user on
the server: it is the same after a reload and in another session. The section of favourites, which is there
only with a favourite, moves as the others; a project dragged among the projects moves no section.
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


def read_stored_sections(
    check: steps.Check, account: ins.Account, with_favorites: bool = False
) -> t.List[str]:
    """The sections in the order the server keeps for the account; the one of favourites, which the sidebar
    shows only when there are some, is left out unless asked for."""
    stored: ins.JSONObject = ins.call_app(
        check.instance.url,
        account,
        "GET",
        f"/workspaces/{check.instance.workspace}/sidebar-preferences/",
    )
    places: t.Dict[str, float] = {
        key.removeprefix("section_"): value["sort_order"]
        for key, value in stored.items()
        if key.startswith("section_") and (with_favorites or key != "section_favorites")
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

    ins.call_app(
        check.instance.url,
        account,
        "POST",
        f"/workspaces/{check.instance.workspace}/user-favorites/",
        {
            "entity_type": "project",
            "entity_identifier": project.id,
            "project_id": project.id,
            "entity_data": {"name": project.name},
        },
    )
    page.reload()
    check.expect(
        "with a favourite the sidebar has a section for favourites; the others keep their order",
        lambda: [name for name in read_sections(page) if name != "Favorites"],
        ["Projects", "Workspace", NO_HEADING],
    )
    carry_section(page, "Favorites", over="Projects", down=0.02)
    page.mouse.up()
    check.expect(
        "that section is dragged as the others, and the server keeps its place too",
        lambda: (
            read_sections(page),
            read_stored_sections(check, account, with_favorites=True),
        ),
        (
            ["Favorites", "Projects", "Workspace", NO_HEADING],
            ["favorites", "projects", "workspace", "personal"],
        ),
    )

    other: ins.Project = check.project({account: ins.ROLE_ADMIN})
    page.reload()
    projects: pw.Locator = section(page, "Projects")

    def read_projects() -> t.List[str]:
        return [
            name
            for name in projects.locator("p").all_inner_texts()
            if name in (project.name, other.name)
        ]

    check.expect(
        "the projects of the user stand in the Projects section",
        lambda: sorted(read_projects()),
        sorted([project.name, other.name]),
    )
    before: t.List[str] = read_projects()
    lower: pw.Locator = projects.get_by_text(before[-1], exact=True)
    upper: pw.Locator = projects.get_by_text(before[0], exact=True)
    # a project is taken by the handle that shows at its left while the pointer is over it
    lower.hover()
    box: t.Optional[pw.FloatRect] = lower.locator(
        "xpath=ancestor::button[1]"
    ).bounding_box()
    assert box is not None
    grip: browser.Point = (box["x"] - 5, box["y"] + box["height"] / 2)
    page.wait_for_function(
        """([x, y]) => {
          const handle = document.elementFromPoint(x, y)?.closest('[aria-label="Drag to rearrange"]');
          return handle && getComputedStyle(handle).opacity === '1';
        }""",
        arg=grip,
    )
    browser.press_and_carry(page, grip)
    browser.carry_to(page, browser.get_point(upper, across=0.3, down=0.1))
    page.mouse.up()
    check.expect(
        "a project dragged above another stands there, and the sections did not move",
        lambda: (read_projects(), read_sections(page)),
        (before[::-1], ["Favorites", "Projects", "Workspace", NO_HEADING]),
    )
    page.context.close()
