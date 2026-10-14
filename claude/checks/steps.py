"""
The steps of a check, and what one run of a check knows.

A step states a rule and compares the whole of what is read with the whole of what is expected. It reads again
until the two are the same or its time is over: the page is given the time it needs, and no step waits by the
clock. A step that fails says what it got and what it expected and leaves a picture of every page of the check.
A check goes on after a failed step, since the steps after it may be about other rules.
"""

import dataclasses as dc
import pathlib as pl
import time
import typing as t

import playwright.sync_api as pw

import instance as ins

# How long a step reads again before it fails. The page answers a person within a second; on a machine that is
# busy with other work a list of a hundred lines can take several.
STEP_TIMEOUT: float = 15
READ_AGAIN_AFTER: float = 0.05


@dc.dataclass(frozen=True)
class Unreadable:
    """What a step got when its read failed: the first line of the error."""

    error: str


def read_or_say_why(read: t.Callable[[], t.Any]) -> t.Any:
    try:
        return read()
    except Exception as error:
        return Unreadable(
            f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"
        )


@dc.dataclass(frozen=True)
class Step:
    rule: str
    failure: t.Optional[str]


@dc.dataclass
class Check:
    name: str
    instance: ins.Instance
    browser: pw.Browser
    directory: pl.Path
    steps: t.List[Step] = dc.field(default_factory=list)
    pages: t.List[pw.Page] = dc.field(default_factory=list)
    projects: t.List[ins.Project] = dc.field(default_factory=list)
    accounts: t.List[ins.Account] = dc.field(default_factory=list)
    # what the pages reported by themselves: errors nobody caught, and requests the server failed
    page_errors: t.List[str] = dc.field(default_factory=list)
    server_errors: t.List[str] = dc.field(default_factory=list)

    def take_pictures(self) -> t.List[str]:
        paths: t.List[str] = []
        page: pw.Page
        for page in self.pages:
            if not page.is_closed():
                path: pl.Path = (
                    self.directory / f"step-{len(self.steps) + 1}-{len(paths)}.png"
                )
                page.screenshot(path=str(path))
                paths.append(str(path))
        return paths

    def fail(self, rule: str, what: str) -> None:
        pictures: str = ", ".join(self.take_pictures())
        self.steps.append(Step(rule, f"{what}\n        pictures: {pictures}"))

    def expect(
        self,
        rule: str,
        read: t.Callable[[], t.Any],
        expected: t.Any,
        timeout: float = STEP_TIMEOUT,
    ) -> None:
        """The rule holds when what `read` gives is what is expected, now or after the page has caught up. A read
        that cannot be made yet, of something the page has not drawn yet, is read again as well."""
        deadline: float = time.monotonic() + timeout
        got: t.Any = read_or_say_why(read)
        while got != expected and time.monotonic() < deadline:
            time.sleep(READ_AGAIN_AFTER)
            got = read_or_say_why(read)
        if got == expected:
            self.steps.append(Step(rule, None))
        else:
            self.fail(rule, f"got      {got!r}\n        expected {expected!r}")

    def expect_stays(
        self,
        rule: str,
        read: t.Callable[[], t.Any],
        expected: t.Any,
        seconds: float,
    ) -> None:
        """The rule holds when what `read` gives is what is expected for all of the given time: for a rule
        that says that something does not happen."""
        deadline: float = time.monotonic() + seconds
        got: t.Any = read()
        while got == expected and time.monotonic() < deadline:
            time.sleep(READ_AGAIN_AFTER)
            got = read()
        if got == expected:
            self.steps.append(Step(rule, None))
        else:
            self.fail(rule, f"got      {got!r}\n        expected {expected!r}")

    def expect_at_least(self, rule: str, got: float, least: float) -> None:
        """The rule holds when a number that was measured on the page is not below the least it may be."""
        if got >= least:
            self.steps.append(Step(rule, None))
        else:
            self.fail(rule, f"got      {got!r}\n        expected at least {least!r}")

    def expect_at_most(self, rule: str, got: float, most: float) -> None:
        """The rule holds when a number that was measured on the page is not above the most it may be."""
        if got <= most:
            self.steps.append(Step(rule, None))
        else:
            self.fail(rule, f"got      {got!r}\n        expected at most {most!r}")

    def account(self, role: int = ins.ROLE_ADMIN) -> ins.Account:
        account: ins.Account = ins.make_account(self.instance, role)
        self.accounts.append(account)
        return account

    def project(
        self, members: t.Dict[ins.Account, int], **fields: t.Any
    ) -> ins.Project:
        project: ins.Project = ins.make_project(self.instance, members, **fields)
        self.projects.append(project)
        return project
