"""
A page of the app has the browser fetch, along with the page itself, the API answers that its code asks for first,
and the code takes those answers: each preloaded answer is one the code asks for, and none is fetched again.
"""

import re
import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import list_layout as ll
import plane_runtime
import steps

# Notes every address that the page's own code asks for, before that code runs. The browser keeps the timings of
# only some hundreds of fetched files by default, fewer than a page fetches, and drops those of the last ones.
RECORD_ASKED_JS: str = """
(() => {
  performance.setResourceTimingBufferSize(100000);
  window.__asked = [];
  const note = (address) => window.__asked.push(new URL(address, location.href).href);
  const open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, address) {
    note(address);
    return open.apply(this, arguments);
  };
  const fetch = window.fetch;
  window.fetch = function (input) {
    note(typeof input === "string" ? input : input.url);
    return fetch.apply(this, arguments);
  };
})();
"""

PRELOADED_JS: str = """
() => performance.getEntriesByType("resource")
  .filter((entry) => entry.initiatorType === "link" && entry.name.includes("/api/"))
  .map((entry) => entry.name)
"""

FETCHED_BY_CODE_JS: str = """
() => performance.getEntriesByType("resource")
  .filter((entry) => entry.initiatorType === "xmlhttprequest" || entry.initiatorType === "fetch")
  .map((entry) => entry.name)
"""


def run(check: steps.Check) -> None:
    account: ins.Account = check.account()
    project: ins.Project = check.project({account: ins.ROLE_ADMIN})
    ins.make_work_items(check.instance, project, [{"name": "a line"}])
    page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/{project.identifier.lower()}/"
    )
    page.context.add_init_script(RECORD_ASKED_JS)
    page.reload()
    ll.line(page, "a line").wait_for()
    expected_preloads: t.List[str] = sorted(
        check.instance.url + path.replace("{re.workspace.1}", check.instance.workspace)
        for path in plane_runtime.PRELOADED_API_REQUESTS_OF_EVERY_PAGE
        + plane_runtime.PRELOADED_API_REQUESTS_OF_A_WORKSPACE_PAGE
    )
    check.expect(
        "the page of a project's work items preloads the first requests of every page and of its workspace",
        lambda: sorted(page.evaluate(PRELOADED_JS)),
        expected_preloads,
    )
    check.expect(
        "the code asks for every answer that was preloaded (preloaded answers it did not ask for)",
        lambda: sorted(
            set(page.evaluate(PRELOADED_JS))
            - set(page.evaluate("() => window.__asked"))
        ),
        [],
    )
    check.expect(
        "the code takes each preloaded answer and fetches none of them again (fetched again)",
        lambda: sorted(
            set(page.evaluate(PRELOADED_JS)) & set(page.evaluate(FETCHED_BY_CODE_JS))
        ),
        [],
        timeout=0,
    )
    # The first part of a page's address goes into the header that names the preloads; a comma, a semicolon or an
    # angle bracket there would add or change preloads, as with this address.
    response: pw.APIResponse = page.request.get(
        check.instance.url + "/x,<https://elsewhere/>;rel=preload/"
    )
    check.expect(
        "a page whose address cannot name a workspace preloads only the first requests of every page",
        lambda: sorted(
            re.findall(
                "<([^>]*)>",
                ",".join(
                    header["value"]
                    for header in response.headers_array
                    if header["name"].lower() == "link"
                ),
            )
        ),
        sorted(plane_runtime.PRELOADED_API_REQUESTS_OF_EVERY_PAGE),
        timeout=0,
    )
