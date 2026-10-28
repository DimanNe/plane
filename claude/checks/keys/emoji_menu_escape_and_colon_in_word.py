"""
In a description, Escape closes the menu of emojis and leaves what was typed, and what is typed on is text, which the
server stores as typed. A ":" inside a word, as in 10:30 or http://x, opens no menu. It goes on after the emojis that
keys/emoji_menu and keys/emoji_menu_tab_and_click put.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import keys_emoji_menu as em
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    # FOR_REVIEWER: the step about ":" inside a word says nothing happens, so it waits for the timers the page started
    # after the check's first key (settle.py). The editor starts the autosave's timer as the page loads, and keys
    # typed within the autosave's pause put that timer off without starting a new one: in a check of its own, right
    # after the load, the step ended after 40 ms instead of waiting for the autosave (1.9 s). After the read of the
    # server about Escape the autosave has saved, so the step waits for the next one, as it did when keys/emoji_menu
    # played every rule (PLANE-112).
    project: ins.Project
    ids: t.Dict[str, str]
    page: pw.Page
    project, ids, page = em.open_description(check)
    em.put_umbrella_with_enter(check, page)
    em.put_thumbs_with_tab_and_click(check, page)
    page.keyboard.type(":umb")
    check.expect("the menu opens again", lambda: em.read_menu(page), em.UMBRELLAS)
    page.keyboard.press("Escape")
    page.keyboard.type("rella")
    check.expect(
        "Escape closes the menu and leaves :umb, and what is typed on is text (menu, stored)",
        lambda: (em.read_menu(page), ll.read_description(check, project, "rainy day")),
        ([], "start ☂ 👎 👍 :umbrella"),
    )
    page.evaluate(em.WATCH_MENU_JS)
    page.keyboard.type(" at 10:30 see http://x")
    check.expect_stays(
        "a ':' inside a word, as in 10:30 and http://x, opens no menu",
        lambda: page.evaluate("() => window.emojiMenuWasDrawn"),
        False,
    )
    page.context.close()
