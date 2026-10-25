"""
In intake ↑ and ↓ show the work item above or below in the list of intake only where no control takes the key: with
the focus on the page itself they do, while on a property, whose menu ↓ opens, in the title and in the description the
key is that control's, and the same work item stays open.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import steps

TITLE: str = "#title-input"
DESCRIPTION: str = "<p>one</p><p>two</p>"
# Where the focus is: in the title, on a line of the description, in the search field of an open menu of a property, on
# a property, or else the element that has it.
FOCUS_JS: str = """
(title) => {
  const element = document.activeElement;
  if (element && element === document.querySelector(title)) return 'in the title';
  if (element?.classList.contains('ProseMirror')) {
    const node = getSelection().focusNode;
    const line = (node instanceof Element ? node : node?.parentElement)?.closest('p');
    return line ? `on the line "${line.textContent}"` : 'in the description, on no line';
  }
  if (element?.closest('[data-select-popup]')) return 'in an open menu';
  if (element?.getAttribute('role') === 'combobox') return `on the property "${element.textContent.trim()}"`;
  return element === document.body ? 'on the page' : (element?.tagName ?? null);
}
"""


def read_open_and_focus(page: pw.Page) -> t.Tuple[str, str]:
    return page.locator(TITLE).input_value(), page.evaluate(FOCUS_JS, TITLE)


def press_and_expect(
    check: steps.Check, page: pw.Page, key: str, rule: str, focus: str
) -> None:
    """The key moves the focus or the caret, and then nothing more happens: the same work item stays open."""
    page.keyboard.press(key)
    check.expect(
        f"{rule} (open work item, focus)",
        lambda: read_open_and_focus(page),
        ("intake two", focus),
    )
    check.expect_stays(
        f"{rule}, and the same work item stays open (open work item, focus)",
        lambda: read_open_and_focus(page),
        ("intake two", focus),
    )


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    # the API makes a project's intake when an update turns it on, not when the project is made with it on
    ins.call_api(
        check.instance, "PATCH", f"/projects/{project.id}/", {"intake_view": True}
    )
    made: t.List[ins.JSONObject] = [
        ins.call_api(
            check.instance,
            "POST",
            f"/projects/{project.id}/intake-issues/",
            {"issue": {"name": name, "description_html": DESCRIPTION}},
        )
        for name in ("intake one", "intake two", "intake three")
    ]
    page: pw.Page = browser.open_page(
        check,
        account,
        f"/{check.instance.workspace}/projects/{project.id}/intake/?currentTab=open&inboxIssueId={made[1]['issue']}",
    )
    check.expect(
        "intake opens at the work item of its address, with the focus on the page (open work item, focus)",
        lambda: read_open_and_focus(page),
        ("intake two", "on the page"),
    )
    # The editor stores a description written through the API in its own form as soon as it shows it, and intake
    # takes no ↑ or ↓ while it shows "Saving...": the steps below would hold without a key of intake heard at all.
    check.expect(
        "the page has stored the description in its editor's form, and is saving nothing (stored as written, saving)",
        lambda: (
            ins.call_api(
                check.instance,
                "GET",
                f"/projects/{project.id}/intake-issues/{made[1]['issue']}/",
            )["issue_detail"]["description_html"]
            == DESCRIPTION,
            page.get_by_text("Saving...").count() > 0,
        ),
        (False, False),
    )
    page.get_by_text("Add labels").click()
    check.expect(
        "a click on a property opens its menu",
        lambda: read_open_and_focus(page),
        ("intake two", "in an open menu"),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes the menu and leaves the focus on the property",
        lambda: read_open_and_focus(page),
        ("intake two", 'on the property "Add labels"'),
    )
    press_and_expect(
        check, page, "ArrowDown", "↓ on a property opens its menu", "in an open menu"
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes the menu again",
        lambda: read_open_and_focus(page),
        ("intake two", 'on the property "Add labels"'),
    )

    page.locator(TITLE).click()
    press_and_expect(
        check, page, "ArrowUp", "↑ in the title stays there", "in the title"
    )
    press_and_expect(
        check, page, "ArrowDown", "↓ in the title stays there", "in the title"
    )

    last_line: t.Optional[pw.FloatRect] = (
        page.locator(".ProseMirror p").filter(has_text="two").first.bounding_box()
    )
    assert last_line is not None
    page.mouse.click(
        last_line["x"] + last_line["width"] - 2,
        last_line["y"] + last_line["height"] / 2,
    )
    check.expect(
        "a click at the end of the description puts the caret on its last line (open work item, focus)",
        lambda: read_open_and_focus(page),
        ("intake two", 'on the line "two"'),
    )
    press_and_expect(
        check,
        page,
        "ArrowUp",
        "↑ in the description goes up a line",
        'on the line "one"',
    )
    press_and_expect(
        check,
        page,
        "ArrowDown",
        "↓ in the description goes down a line",
        'on the line "two"',
    )
    # a click where nothing takes the focus gives it to the page; the newest work item is at the top of the list
    page.get_by_text("Properties", exact=True).click()
    page.keyboard.press("ArrowDown")
    check.expect(
        "with the focus on the page ↓ shows the work item below in the list (open work item, focus)",
        lambda: read_open_and_focus(page),
        ("intake one", "on the page"),
    )
    page.context.close()
