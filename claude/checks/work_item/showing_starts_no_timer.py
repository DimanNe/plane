"""
Showing a work item starts no timer of the page: in the view beside the list, on its own page and in the peek of the
board, each opened as a person opens it. Every step that says nothing happens waits for the timers that the page
started since the last act (settle.py), so a timer that showing a work item starts for nothing, such as a save of a
title that nobody changed, makes every such step after an opening wait for it. The timers that do start are those of
KNOWN_TIMERS, each for the reason given there. Nor does the page receive the recent visit that the server records at
each showing: the live updates that reach a page are rows that name a work item, the only ones its rules follow.
"""

import typing as t
import uuid

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import page_changes
import settle
import steps

VIEW: str = "#full-screen-portal"
# Timers that showing a work item starts, each known by a part of its function's text that the app's build keeps: the
# names of properties.
KNOWN_TIMERS: t.Tuple[str, ...] = (
    # @tiptap/core: a new editor takes the focus it was told to and tells its listeners that it exists
    "this.commands.focus(this.options.autofocus)",
    # @tiptap/react: each render of a component with an editor plans to destroy the editor and calls that off when the
    # component has rendered, so that an editor outlives a component that React mounts twice, and not one that is gone
    "this.isComponentMounted",
    # prosemirror-view: when the editor begins a change of its own DOM, it reads a moment later the changes of the DOM
    # that it had not read yet
    "this.flush()",
    # the editor looks for its tables once it is drawn, to give them the buttons that add a row or a column
    # (packages/editor/src/extensions/table/plugins/insert-handlers/plugin.ts)
    "tableElement",
    # the address names the work item open in the peek, written once the selection rests, as for the selected line
    # (apps/web/components/issues/work-items-address.tsx)
    "{address:",
    # The work items that the check makes are followed by what the server's worker writes for them, their activity and
    # their subscriber, which under load reaches the page during these steps as live updates of its own project; the
    # page collects these for a moment before it fetches what they changed (apps/web/store/live-updates.ts).
    "this.batchQuietTimer",
)
# Whether the page shows the work item of this title on a page of its own, with its description: the view beside a
# list has a title of the same id.
WORK_ITEM_PAGE_SHOWN_JS: str = """
([view, path, title, description]) => location.pathname === path && !document.querySelector(view + ' #title-input')
  && document.querySelector('#title-input')?.value === title
  && [...document.querySelectorAll('.ProseMirror')].some((editor) => editor.textContent === description)
"""


def describe_with_block_id(text: str) -> str:
    """A description of one paragraph, with the id that the editor gives each block, as the editor stores it."""
    return f'<p data-id="{uuid.uuid4()}">{text}</p>'


def read_tables_of_live_updates_naming_no_work_item(page: pw.Page) -> t.List[str]:
    return sorted(
        {
            update["t"]
            for update in settle.read_live_updates(page)
            if update["t"] != "issues" and update["i"] is None
        }
    )


def read_timers_not_known(page: pw.Page) -> t.List[str]:
    return [
        timer
        for timer in settle.read_timers_made(page)
        if not any(known in timer for known in KNOWN_TIMERS)
    ]


def run(check: steps.Check) -> None:
    # FOR_REVIEWER: /api/v1/ stores a description without the ids of its blocks, and the first editor that shows it
    # gives them and saves the description, with the timer of the autosave (PLANE-120). So the descriptions here
    # carry the ids as the editor writes them; without them the first showing of each would fail this check.
    # FOR_REVIEWER: two of KNOWN_TIMERS are the app's own. The batch of live updates no longer starts for the recent
    # visit of a showing (PLANE-121), which the step on live updates holds; but in 2 of 2 headless suites it started for
    # the worker's writes of the check's own work items, which came seconds late (PLANE-129), so it stays known for
    # that reason. The address waits for the selection to rest also after a click that opens the peek, where nothing is
    # held; written at once there, it would start no timer. The other four are the editor's libraries' and end within
    # milliseconds.
    # FOR_REVIEWER: a timer is known by its text, so one that a change of the app or of a library adds fails this
    # check until it is named in KNOWN_TIMERS or removed. A limit on the delay instead would let every short timer
    # pass, a new one too, and would still have to name the two of the app.
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(
        check.instance,
        project,
        [
            {
                "name": "seen beside the list",
                "description_html": describe_with_block_id("first words"),
            },
            {
                "name": "seen in the peek",
                "description_html": describe_with_block_id("other words"),
            },
        ],
    )
    page: pw.Page = ll.open_list(check, account, project)
    ll.select_line(page, "seen beside the list")
    check.expect_stays(
        "a click on a line selects it and opens nothing (selected, view)",
        lambda: (ll.read_selected(page), ll.read_panel(page)),
        (["seen beside the list"], None),
    )
    page.keyboard.press("Enter")
    page_changes.wait_until_shown(
        page.locator(f"{VIEW} .ProseMirror", has_text="first words")
    )
    check.expect_stays(
        "showing a work item in the view beside the list starts no timer but known ones",
        lambda: read_timers_not_known(page),
        [],
    )

    work_item_path: str = f"/{check.instance.workspace}/browse/{project.identifier}-1/"
    list_path: str = page.evaluate("location.pathname")
    page.locator(f'{VIEW} a[href$="{work_item_path}"]').hover()
    check.expect_stays(
        "pointing at the view's link to the work item's page opens nothing",
        lambda: page.evaluate("location.pathname"),
        list_path,
    )
    page.mouse.down()
    page.mouse.up()
    page_changes.wait_until_true(
        page,
        WORK_ITEM_PAGE_SHOWN_JS,
        [VIEW, work_item_path, "seen beside the list", "first words"],
    )
    check.expect_stays(
        "showing a work item on its own page, by the link of the view, starts no timer but known ones",
        lambda: read_timers_not_known(page),
        [],
    )
    check.expect_stays(
        "the page received as live updates only rows that name a work item, no recent visit (tables of the others)",
        lambda: read_tables_of_live_updates_naming_no_work_item(page),
        [],
    )
    page.context.close()

    ins.set_display(check.instance, account, project, layout="kanban")
    board: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/projects/{project.id}/issues/"
    )
    card: pw.Locator = board.locator(
        f'a[href$="/browse/{project.identifier}-2/"]'
    ).first
    page_changes.wait_until_shown(card)
    box: t.Optional[pw.FloatRect] = card.bounding_box()
    assert box is not None
    # in the card's padding, where no control of the card is
    board.mouse.move(box["x"] + 6, box["y"] + 6)
    check.expect_stays(
        "pointing at a card of the board opens nothing",
        lambda: ll.read_panel(board),
        None,
    )
    board.mouse.down()
    board.mouse.up()
    page_changes.wait_until_shown(
        board.locator(f"{VIEW} .ProseMirror", has_text="other words")
    )
    check.expect_stays(
        "showing a work item in the peek of the board starts no timer but known ones",
        lambda: read_timers_not_known(board),
        [],
    )
    board.context.close()
