"""
In a description, ":" at the start of a word and the first letters of an emoji's shortcode, or of a word of it, open a
menu of the emojis that match, best first: :umb offers ☂ (umbrella) before 🏖 (beach_umbrella). Enter puts the first
in place of what was typed, and the server stores it. So it is in a comment, which Ctrl+Enter then sends with the
emoji; a comment that ends in ":)", which matches no emoji, opens no menu and is sent by Ctrl+Enter.

The checks named after this one go on from here in a description (keys_emoji_menu.py) and play the menu in the view
beside the list; keys/emoji_menu_in_title plays it in the titles.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import keys_emoji_menu as em
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    # FOR_REVIEWER: since PLANE-84 a ":" in a title opens the same menu, and keys/emoji_menu_in_title checks the
    # titles; these checks play the editors of a description and of a comment.
    project: ins.Project
    ids: t.Dict[str, str]
    page: pw.Page
    project, ids, page = em.open_description(check)
    em.put_umbrella_with_enter(check, page)
    check.expect(
        "Enter puts the first, ☂, in place of :umb, and the server stores it",
        lambda: ll.read_description(check, project, "rainy day"),
        "start ☂ ",
    )

    comment: pw.Locator = page.locator('.ProseMirror[contenteditable="true"]').last
    comment.click()
    page.keyboard.type("see :umb")
    check.expect(
        "in a comment :umb offers the umbrellas",
        lambda: em.read_menu(page),
        em.UMBRELLAS,
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
    page.evaluate(em.WATCH_MENU_JS)
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
    page.context.close()
