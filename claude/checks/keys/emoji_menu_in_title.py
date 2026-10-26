"""
In the title of a work item, ":" at the start of a word and the first letters of an emoji's shortcode open the
editor's menu of the emojis that match, best first, as in a description. Enter, ↓ and Tab, or a click put the chosen
emoji in place of what was typed, and the server stores it as text of the title. While the menu shows, it takes these
keys before the title: Enter neither saves the line edited in place nor goes on in the description, ↓ chooses in the
menu and does not go on in the description either, and Escape closes the menu and leaves the text, not the view
beside the list; then Escape and ↓ are the title's again. A ":" inside a word, as in 10:30, http://x or a:b, opens no
menu, and Ctrl+Enter saves the dialog of N I whose title ends in ":)". So it is in a line of the list edited in place,
in the view beside the list, and in the dialog of N I.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import list_layout as ll
import page_changes
import steps

MENU_ITEM: str = '[id^="emoji-item-"]'
LINE_TITLE: str = f"{ll.LINE} input"
DIALOG_TITLE: str = f'{ll.CREATE_DIALOG} input[name="name"]'
# Where the caret of the dialog of N I is: in its title, in its description, or the element it is in.
CARET_IN_DIALOG_JS: str = """
() => {
  const element = document.activeElement;
  if (!element?.closest('[role="dialog"]')) return element?.tagName ?? null;
  if (element.name === 'name') return 'in the title';
  return element.classList.contains('ProseMirror') ? 'in the description' : element.tagName;
}
"""
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


def read_title(page: pw.Page, selector: str) -> t.Optional[str]:
    """What the title holds, and whether the caret is still in it; None when the title is not there."""
    title: pw.Locator = page.locator(selector)
    if not title.count():
        return None
    has_caret: bool = title.evaluate("(element) => element === document.activeElement")
    return title.input_value() + ("" if has_caret else " (no caret)")


def run(check: steps.Check) -> None:
    # FOR_REVIEWER: the work item's own page and intake show the title of the view beside the list
    # (components/issues/title-input.tsx), and the quick add of the other layouts and intake's dialog of a new work
    # item a field that takes the menu in the same way; this check goes through the three titles the list has.
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance, project, [{"name": "rainy day"}, {"name": "windy day"}]
    )
    page: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.line(page, "rainy day").locator("p").first.click()
    page_changes.wait_until_shown(page.locator(LINE_TITLE))
    page.keyboard.press("End")
    page.keyboard.type(" :umb")
    check.expect(
        "in a line's title edited in place :umb offers the umbrellas, those with a shortcode that begins so first",
        lambda: read_menu(page),
        UMBRELLAS,
    )
    page.keyboard.press("Enter")
    check.expect(
        "Enter puts the first, ☂, in place of :umb, and the line stays edited (menu, title)",
        lambda: (read_menu(page), read_title(page, LINE_TITLE)),
        ([], "rainy day ☂ "),
    )
    page.keyboard.press("Enter")
    check.expect(
        "a second Enter is the title's: it ends the editing, and the server stores ☂ in the title",
        lambda: (
            read_title(page, LINE_TITLE),
            ins.read_work_item_names(check.instance, project),
        ),
        (None, ["rainy day ☂", "windy day"]),
    )

    ll.select_line(page, "windy day")
    page.keyboard.press("Enter")
    page_changes.wait_until_shown(page.locator(ll.PANEL_TITLE))
    page.locator(ll.PANEL_TITLE).click()
    page.keyboard.press("End")
    page.keyboard.type(" :thumbs")
    check.expect(
        "in the title of the view beside the list :thumbs offers thumbs up and down, by shortcodes other than their names",
        lambda: read_menu(page),
        ["👍 :+1:", "👎 :-1:"],
    )
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Tab")
    page.keyboard.type(":+1")
    check.expect(
        ":+1 offers thumbs up, after ↓ and Tab put the second, 👎, in the title (menu, title)",
        lambda: (read_menu(page), read_title(page, ll.PANEL_TITLE)),
        (["👍 :+1:"], "windy day 👎 :+1"),
    )
    page.locator(MENU_ITEM).first.click()
    page.keyboard.type("end :umb")
    check.expect(
        "a click puts the one clicked, 👍; the caret stays in the title, where :umb opens the menu again (menu, title)",
        lambda: (read_menu(page), read_title(page, ll.PANEL_TITLE)),
        (UMBRELLAS, "windy day 👎 👍 end :umb"),
    )
    page.keyboard.press("Escape")
    check.expect(
        "Escape closes the menu, not the view, and leaves :umb (menu, view)",
        lambda: (read_menu(page), read_title(page, ll.PANEL_TITLE)),
        ([], "windy day 👎 👍 end :umb"),
    )
    page.keyboard.press("Escape")
    check.expect(
        "a second Escape is the title's again: the view closes, and the server stores 👎 and 👍 in the title",
        lambda: (
            ll.read_panel(page),
            ins.read_work_item_names(check.instance, project),
        ),
        (None, ["rainy day ☂", "windy day 👎 👍 end :umb"]),
    )

    ll.open_create_dialog(page)
    page.keyboard.type("fix :umb")
    check.expect(
        "in the title of the dialog of N I :umb offers the umbrellas",
        lambda: read_menu(page),
        UMBRELLAS,
    )
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    check.expect(
        "↓ chooses the second, ☔, and Enter puts it there; neither goes on in the description",
        lambda: (read_menu(page), read_title(page, DIALOG_TITLE)),
        ([], "fix ☔ "),
    )
    page.evaluate(WATCH_MENU_JS)
    page.keyboard.type("at 10:30 see http://x a:b :)")
    page.keyboard.press("Control+Enter")
    check.expect(
        "10:30, http://x and a:b open no menu, and Ctrl+Enter saves the title that ends in :) (menu drawn, stored)",
        lambda: (
            page.evaluate("() => window.emojiMenuWasDrawn"),
            ins.read_work_item_names(check.instance, project),
        ),
        (
            False,
            [
                "fix ☔ at 10:30 see http://x a:b :)",
                "rainy day ☂",
                "windy day 👎 👍 end :umb",
            ],
        ),
    )

    ll.open_create_dialog(page)
    page.keyboard.type("calm :umb")
    check.expect("the menu opens again", lambda: read_menu(page), UMBRELLAS)
    page.keyboard.press("Escape")
    page.keyboard.press("ArrowDown")
    check.expect(
        "after Escape, ↓ on the title's last line goes on in the description, and leaves :umb (menu, caret, title)",
        lambda: (
            read_menu(page),
            page.evaluate(CARET_IN_DIALOG_JS),
            page.locator(DIALOG_TITLE).input_value(),
        ),
        ([], "in the description", "calm :umb"),
    )
    page.context.close()
