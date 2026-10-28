"""
In the description of the view beside the list, ":" opens the menu of emojis too. Escape closes the menu, not the
view, and leaves what was typed; a second Escape is the view's again and closes it.
"""

import playwright.sync_api as pw

import instance as ins
import keys_emoji_menu as em
import list_layout as ll
import page_changes
import steps


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {"name": "rainy day", "description_html": "<p>start</p>"},
            {"name": "windy day", "description_html": "<p>start</p>"},
        ],
    )
    beside: pw.Page = ll.open_list(check, account, project, group_by=None)
    ll.select_line(beside, "windy day")
    beside.keyboard.press("Enter")
    page_changes.wait_until_shown(beside.locator(ll.PANEL_TITLE))
    beside.locator("#full-screen-portal .ProseMirror", has_text="start").click()
    beside.keyboard.press("Control+End")
    beside.keyboard.type(" :umb")
    check.expect(
        "in the view beside the list :umb opens the menu",
        lambda: em.read_menu(beside),
        em.UMBRELLAS,
    )
    beside.keyboard.press("Escape")
    check.expect(
        "Escape there closes the menu, not the view, and leaves :umb (menu, view, description)",
        lambda: (
            em.read_menu(beside),
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
    beside.context.close()
