"""
In a description and in a comment, ":" at the start of a word and the first letters of an emoji's shortcode, or of
a word of it, open a menu of the emojis that match, best first: :umb offers ☂ (umbrella) before 🏖 (beach_umbrella).
Enter, ↓ and Tab, or a click put the chosen emoji in place of what was typed, and the server stores it. Escape
closes the menu and leaves the text; a second Escape is the page's again. A ":" inside a word, as in 10:30 or
http://x, opens no menu, and a comment that ends in ":)", which matches no emoji, is sent by Ctrl+Enter.
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import steps

MENU_ITEM: str = '[id^="emoji-item-"]'
# Notes whether the emoji menu has been drawn at any moment since, so that a menu that comes and goes while keys
# are typed is seen too.
WATCH_MENU_JS: str = """
() => {
  window.emojiMenuWasDrawn = false;
  window.emojiMenuWatch ??= new MutationObserver(() => {
    if (document.querySelector('[id^="emoji-item-"]')) window.emojiMenuWasDrawn = true;
  });
  window.emojiMenuWatch.observe(document.body, { childList: true, subtree: true });
}
"""
UMBRELLAS: t.List[str] = [
    "☂ :open_umbrella:",
    "☔ :umbrella:",
    "⛱ :parasol_on_ground:",
    "🏖 :beach_umbrella:",
    "🌂 :closed_umbrella:",
]


def read_menu(page: pw.Page) -> t.List[str]:
    """The emojis the menu offers, in its order, as drawn: each emoji and its shortcode."""
    return [
        " ".join(text.split()) for text in page.locator(MENU_ITEM).all_inner_texts()
    ]


def run(check: steps.Check) -> None:
    # FOR_REVIEWER: titles are plain text fields, not editors, so a ":" in a title stays text, as the task said.
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "rainy day", "description_html": "<p>start</p>"},
            {"name": "windy day", "description_html": "<p>start</p>"},
        ],
    )
    page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/browse/{project.identifier}-1/"
    )
    description: pw.Locator = page.locator(".ProseMirror", has_text="start")
    description.click()
    page.keyboard.press("Control+End")
    page.keyboard.type(" :umb")
    check.expect(
        "in a description :umb offers the umbrellas, those with a shortcode that begins so first",
        lambda: read_menu(page),
        UMBRELLAS,
    )
    page.keyboard.press("Enter")
    check.expect(
        "Enter puts the first, ☂, in place of :umb, and the server stores it",
        lambda: ll.read_description(check, project, "rainy day"),
        "start ☂ ",
    )
    page.keyboard.type(":thumbs")
    check.expect(
        ":thumbs offers thumbs up and down, by shortcodes other than their names",
        lambda: read_menu(page),
        ["👍 :+1:", "👎 :-1:"],
    )
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Tab")
    page.keyboard.type(":+1")
    check.expect(":+1 offers thumbs up", lambda: read_menu(page), ["👍 :+1:"])
    page.locator(MENU_ITEM).first.click()
    check.expect(
        "↓ and Tab put the second, 👎, and a click the one clicked, 👍, and the server stores them",
        lambda: ll.read_description(check, project, "rainy day"),
        "start ☂ 👎 👍 ",
    )
    page.keyboard.type(":umb")
    check.expect("the menu opens again", lambda: read_menu(page), UMBRELLAS)
    page.keyboard.press("Escape")
    page.keyboard.type("rella")
    check.expect(
        "Escape closes the menu and leaves :umb, and what is typed on is text (menu, stored)",
        lambda: (read_menu(page), ll.read_description(check, project, "rainy day")),
        ([], "start ☂ 👎 👍 :umbrella"),
    )
    page.evaluate(WATCH_MENU_JS)
    page.keyboard.type(" at 10:30 see http://x")
    check.expect_stays(
        "a ':' inside a word, as in 10:30 and http://x, opens no menu",
        lambda: page.evaluate("() => window.emojiMenuWasDrawn"),
        False,
    )

    comment: pw.Locator = page.locator('.ProseMirror[contenteditable="true"]').last
    comment.click()
    page.keyboard.type("see :umb")
    check.expect(
        "in a comment :umb offers the umbrellas", lambda: read_menu(page), UMBRELLAS
    )
    page.keyboard.press("Enter")
    page.keyboard.press("Control+Enter")
    check.expect(
        "Enter puts ☂ in the comment, and Ctrl+Enter sends it with ☂ and empties the editor",
        lambda: (
            ll.read_comments(check, project, ids["rainy day"]),
            comment.inner_text().strip(),
        ),
        ([["see ☂ "]], ""),
    )
    comment.click()
    page.evaluate(WATCH_MENU_JS)
    page.keyboard.type("thanks :)")
    page.keyboard.press("Control+Enter")
    check.expect(
        "a comment that ends in :) opens no menu and is sent by Ctrl+Enter (menu drawn, comment)",
        lambda: (
            page.evaluate("() => window.emojiMenuWasDrawn"),
            ll.read_comments(check, project, ids["rainy day"])[-1],
        ),
        (False, ["thanks :)"]),
    )

    beside: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(beside, "windy day")
    beside.keyboard.press("Enter")
    beside.locator(ll.PANEL_TITLE).wait_for()
    beside.locator("#full-screen-portal .ProseMirror", has_text="start").click()
    beside.keyboard.press("Control+End")
    beside.keyboard.type(" :umb")
    check.expect(
        "in the view beside the list :umb opens the menu",
        lambda: read_menu(beside),
        UMBRELLAS,
    )
    beside.keyboard.press("Escape")
    check.expect(
        "Escape there closes the menu, not the view, and leaves :umb (menu, view, description)",
        lambda: (
            read_menu(beside),
            ll.read_panel(beside),
            beside.locator(
                "#full-screen-portal .ProseMirror", has_text="start"
            ).inner_text(),
        ),
        ([], "windy day", "start :umb"),
    )
    beside.keyboard.press("Escape")
    check.expect(
        "a second Escape is the view's again: it closes",
        lambda: ll.read_panel(beside),
        None,
    )
    page.context.close()
    beside.context.close()
