"""
In a description, the menu of emojis also finds an emoji by a shortcode other than its name: :thumbs offers 👍 (+1)
and 👎 (-1). ↓ and Tab put the second, and a click the one clicked, in place of what was typed, and the server stores
them. It goes on after Enter has put ☂, as in keys/emoji_menu.
"""

import typing as t

import playwright.sync_api as pw

import instance as ins
import keys_emoji_menu as em
import list_layout as ll
import steps


def run(check: steps.Check) -> None:
    project: ins.Project
    ids: t.Dict[str, str]
    page: pw.Page
    project, ids, page = em.open_description(check)
    em.put_umbrella_with_enter(check, page)
    em.put_thumbs_with_tab_and_click(check, page)
    check.expect(
        "↓ and Tab put the second, 👎, and a click the one clicked, 👍, and the server stores them",
        lambda: ll.read_description(check, project, "rainy day"),
        "start ☂ 👎 👍 ",
    )
    page.context.close()
