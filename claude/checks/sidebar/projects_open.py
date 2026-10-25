"""
Every project in the sidebar is open, with its pages under it, until the user folds it; a click on a project folds
it and opens it again. A folded project stays folded while the user goes to other pages of the app.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import page_changes
import steps

# For each project, by its name: whether its button in the sidebar says it is open, and whether its pages are shown,
# of which Cycles stands only under the project.
PROJECTS_JS: str = """
(projects) => projects.map(([name, id]) => {
  const sidebar = document.querySelector('[aria-label="Main sidebar"]');
  const button = [...sidebar.querySelectorAll('button[aria-expanded]')]
    .find((candidate) => candidate.querySelector('p')?.textContent.trim() === name);
  return [
    name,
    button?.getAttribute('aria-expanded') === 'true',
    sidebar.querySelector(`a[href$="/projects/${id}/cycles/"]`) !== null,
  ];
})
"""


def read_projects(
    page: pw.Page, projects: t.Sequence[ins.Project]
) -> t.List[t.List[t.Any]]:
    return page.evaluate(
        PROJECTS_JS, [[project.name, project.id] for project in projects]
    )


def project_button(page: pw.Page, project: ins.Project) -> pw.Locator:
    return (
        page.get_by_role("complementary", name="Main sidebar")
        .locator("button[aria-expanded]")
        .filter(has=page.get_by_text(project.name, exact=True))
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    first: ins.Project = check.project({account: ins.ROLE_ADMIN}, cycle_view=True)
    second: ins.Project = check.project({account: ins.ROLE_ADMIN}, cycle_view=True)
    projects: t.List[ins.Project] = [first, second]
    page: pw.Page = browser.open_page(check, account, f"/{check.instance.workspace}/")
    page_changes.wait_until_true(
        page,
        "(names) => names.every((name) => [...document.querySelectorAll('[aria-label=\"Main sidebar\"] p')]"
        ".some((text) => text.textContent.trim() === name))",
        arg=[first.name, second.name],
    )

    check.expect(
        "on a page of no project, every project in the sidebar is open, with its pages under it",
        lambda: read_projects(page, projects),
        [[first.name, True, True], [second.name, True, True]],
    )
    project_button(page, second).click()
    check.expect(
        "a click on a project folds it, and only it",
        lambda: read_projects(page, projects),
        [[first.name, True, True], [second.name, False, False]],
    )
    page.get_by_role("complementary", name="Main sidebar").locator(
        f'a[href$="/projects/{first.id}/cycles/"]'
    ).click()
    page.wait_for_url(f"**/projects/{first.id}/cycles/")
    check.expect(
        "on another page of the app the folded project stays folded",
        lambda: read_projects(page, projects),
        [[first.name, True, True], [second.name, False, False]],
    )
    project_button(page, second).click()
    check.expect(
        "a click on a folded project opens it again",
        lambda: read_projects(page, projects),
        [[first.name, True, True], [second.name, True, True]],
    )
    page.context.close()
