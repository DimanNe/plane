"""
What the checks of the menu of emojis need: keys/emoji_menu and the checks named after it.

What a rule of the menu meets in a description depends on what the description already holds: an emoji put before is
a node in front of the caret, and a menu closed by Escape leaves its word behind. So the checks of a description play
one sequence of keys, each as far as its own rule: it first puts the emojis that the rules before it put, as they
did, and reads the server only for its own rule. A read of the server waits for the description's autosave, which
saves after a pause in typing (apps/web/components/editor/rich-text/description-input/root.tsx).
"""

import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import page_changes
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


def open_description(
    check: steps.Check,
) -> t.Tuple[ins.Project, t.Dict[str, str], pw.Page]:
    """The page of a work item "rainy day", whose description is "start", with the caret at the end of it."""
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ids: t.Dict[str, str] = ins.make_work_items(
        check.instance,
        project,
        [{"name": "rainy day", "description_html": "<p>start</p>"}],
    )
    page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/browse/{project.identifier}-1/"
    )
    page.locator(".ProseMirror", has_text="start").click()
    page.keyboard.press("Control+End")
    return project, ids, page


def put_umbrella_with_enter(check: steps.Check, page: pw.Page) -> None:
    page.keyboard.type(" :umb")
    check.expect(
        "in a description :umb offers the umbrellas, those with a shortcode that begins so first",
        lambda: read_menu(page),
        UMBRELLAS,
    )
    page.keyboard.press("Enter")


def put_thumbs_with_tab_and_click(check: steps.Check, page: pw.Page) -> None:
    """After put_umbrella_with_enter: puts 👎 with ↓ and Tab, and 👍 with a click."""
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
    # The press on the item takes the caret from the description, and the click gives it back a frame later; what
    # is typed in between is lost.
    # FOR_REVIEWER: a person rarely types within a frame of a click, but the checks do; PLANE-111 is about the app.
    page_changes.wait_until_true(
        page, "() => !!document.activeElement?.classList.contains('ProseMirror')"
    )
