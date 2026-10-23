"""
What the addresses/work_items* checks read: what a page shows, by which its address is judged.
"""

import typing as t

import playwright.sync_api as pw

import list_layout as ll

Shown: t.TypeAlias = t.Tuple[str, t.Optional[str], t.List[str], t.Optional[str]]
LAYOUT_JS: str = """
() => [...document.querySelectorAll('button[aria-label$=" Layout"]')]
  .find((button) => button.className.includes('bg-layer-transparent-active'))
  ?.getAttribute('aria-label').replace(' Layout', '') ?? null
"""


def read_page(page: pw.Page) -> Shown:
    """The address, the layout, the selected lines of the list, the title in the view of one work item."""
    return (
        page.evaluate("location.pathname"),
        page.evaluate(LAYOUT_JS),
        ll.read_selected(page),
        ll.read_panel(page),
    )


def choose_layout(page: pw.Page, layout: str) -> None:
    page.get_by_role("button", name=f"{layout} Layout").click()


def read_main_text(page: pw.Page) -> str:
    return page.locator("main").last.inner_text()
