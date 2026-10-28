#!/usr/bin/env python3
"""
Runs the checks of the web app against running instances, and tells which rule of the app no longer holds.

    claude/checks/run.py --run-dir RUN_DIR                      every check, headless
    claude/checks/run.py --run-dir RUN_DIR --windows list       the checks of the list, in real Chrome windows
    claude/checks/run.py --run-dir A --run-dir B list/delete_key sidebar
    claude/checks/run.py --list

A check is a file GROUP/NAME.py beside this one; it is named GROUP/NAME, and GROUP names all of a group. Its
first lines say the rule it guards. Each step prints as the rule it checks; the status is 1 when a step failed.

An instance is one started by scripts/plane_runtime.py; nothing but its run directory is needed. The checks are
spread over the run directories given, several at once on each, those that took longest when they last ran start
first (see order_longest_first). Nothing of a run outlives it, however it ends (see run_scope.py).

A check makes its own accounts and its own projects, in a workspace of the run, and removes the projects when
it has passed. What a failed check left stays, with the way to sign in printed beside the failure, and so does
what a killed run left; the next run on that instance removes both first. The accounts stay, each as a row
of the server's users. An instance serves one run at a time: a second run ends at once and says so.
"""

import abc
import argparse
import atexit
import concurrent.futures
import dataclasses as dc
import gc
import importlib.util
import json
import math
import multiprocessing
import os
import pathlib as pl
import shutil
import sys
import time
import traceback
import types
import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import run_scope
import steps

CHECKS: pl.Path = pl.Path(__file__).resolve().parent
# Errors the pages are known to report, which say nothing about the rule a check guards.
KNOWN_PAGE_ERRORS: t.Tuple[str, ...] = (
    # A layout that is left while its request for the work items is under way: the store cancels that request
    # when the next layout asks (base-issues.store.ts, clear), the service throws on what the server answered,
    # which is nothing (issue.service.ts), and the layout that had asked does not catch it. Upstream's.
    "undefined (at ",
)


@dc.dataclass(frozen=True)
class Outcome:
    name: str
    run_dir: pl.Path
    steps: t.List[steps.Step]
    seconds: float
    # how a person finds what a failed check left
    left: t.List[str]


def find_checks(names: t.Sequence[str]) -> t.List[str]:
    """The checks named, or all of them: a name is GROUP/NAME, or GROUP for every check of a group."""
    known: t.List[str] = sorted(
        f"{path.parent.name}/{path.stem}" for path in CHECKS.glob("*/*.py")
    )
    if not names:
        return known
    found: t.List[str] = []
    name: str
    for name in names:
        matching: t.List[str] = [
            check for check in known if name in (check, check.split("/")[0])
        ]
        if not matching:
            raise SystemExit(
                f"No check or group {name!r}; there are: {', '.join(known)}"
            )
        found += [check for check in matching if check not in found]
    return found


def load_check(name: str) -> types.ModuleType:
    spec: t.Any = importlib.util.spec_from_file_location(
        name.replace("/", "_"), CHECKS / f"{name}.py"
    )
    module: types.ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_rule(module: types.ModuleType) -> str:
    return " ".join((module.__doc__ or "").strip().split("\n\n")[0].split())


# how much of what an error says is printed: Playwright goes on to list every element it looked at
ERROR_LINES: int = 4


def describe_error(error: Exception) -> str:
    """The error, and the lines of the checks it came through; those of Playwright and Python say nothing."""
    own: t.List[traceback.FrameSummary] = [
        frame
        for frame in traceback.extract_tb(error.__traceback__)
        if CHECKS in pl.Path(frame.filename).parents
        and frame.name != "run_steps_of_check"
    ]
    said: t.List[str] = "".join(traceback.format_exception_only(error)).splitlines()
    return "".join(traceback.format_list(own)) + "\n".join(said[:ERROR_LINES])


def run_steps_of_check(check: steps.Check, module: types.ModuleType) -> None:
    try:
        module.run(check)
    except Exception as error:
        # something a step needed was not there: a control to press, a line to point at
        check.fail("the check runs to its end", describe_error(error))
    check.expect(
        "no page reported an error of its own",
        lambda: [
            error
            for error in check.page_errors
            if not error.startswith(KNOWN_PAGE_ERRORS)
        ],
        [],
        timeout=0,
    )
    check.expect(
        "the server failed no request", lambda: check.server_errors, [], timeout=0
    )


def skip_garbage_collection_at_exit() -> None:
    """Run by each process of the checks as it starts. Python's exit searches every object that the process still
    holds for cycles of garbage, and the end of a run waits for that search in each of its processes; the end of the
    process frees those objects anyway."""
    # FOR_REVIEWER: measured over a whole run, headless 7×14: the pools' processes took the shutdown's sentinel
    # within 14 ms, and the pools' shutdowns returned 230-350 ms later; with this, 95-110 ms. Ending the processes
    # without any of Python's exit (os._exit), 85-97 ms, would also lose what a check printed last and the exit code.
    atexit.register(gc.freeze)


def run_check(name: str, instance: ins.Instance, is_real_window: bool) -> Outcome:
    """Runs one check in a browser of its own. Called in a process of its own."""
    start: float = time.monotonic()
    module: types.ModuleType = load_check(name)
    directory: pl.Path = instance.run_dir / "checks" / name.replace("/", "-")
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    # the browser keeps its files of the moment here and not in a /tmp that may be small
    os.environ["TMPDIR"] = str(directory)
    playwright: pw.Playwright
    opened: pw.Browser
    check: t.Optional[steps.Check] = None
    try:
        with pw.sync_playwright() as playwright:
            with browser.open_browser(playwright, is_real_window, directory) as opened:
                check = steps.Check(name, instance, opened, directory)
                run_steps_of_check(check, module)
    except Exception as error:
        # a busy machine can keep the check's browser from starting or from stopping: this check fails, and the run
        # goes on with the others
        failed: steps.Step = steps.Step(
            "the check's browser starts and stops", describe_error(error)
        )
        done: t.List[steps.Step] = check.steps if check else []
        return Outcome(
            name, instance.run_dir, done + [failed], time.monotonic() - start, []
        )
    assert check is not None
    left: t.List[str] = []
    if all(step.failure is None for step in check.steps):
        project: ins.Project
        for project in check.projects:
            ins.remove_project(instance, project)
        shutil.rmtree(directory)
    else:
        left = [
            f"{instance.url}/{instance.workspace}/projects/{project.id}/issues/"
            for project in check.projects
        ] + [f"as {account.email} / {account.password}" for account in check.accounts]
    return Outcome(name, instance.run_dir, check.steps, time.monotonic() - start, left)


def print_outcome(outcome: Outcome) -> None:
    failed: int = sum(step.failure is not None for step in outcome.steps)
    print(
        f"{outcome.name}: {len(outcome.steps)} steps, {failed} failed, {outcome.seconds:.0f} s"
    )
    step: steps.Step
    for step in outcome.steps:
        if step.failure is None:
            print(f"  ok    {step.rule}")
        else:
            print(f"  FAIL  {step.rule}\n        {step.failure}")
    if outcome.left:
        print(f"  left for a look: {' '.join(outcome.left)}")
    sys.stdout.flush()


# How long each check of the runs that an instance served took, kept in the instance's run directory beside the
# directories of the checks that failed there: {name: {"seconds": ..., "written": ...}}, `written` being the moment
# the run wrote it.
SECONDS_TAKEN: str = "seconds-taken.json"


def read_seconds_taken(instances: t.Sequence[ins.Instance]) -> t.Dict[str, float]:
    """How long each check took in the last run that one of the instances served. A check that none of their runs
    had is not there."""
    # FOR_REVIEWER: the times are run_check's own (Outcome.seconds), kept in each instance's run directory, where
    # run.py keeps the rest of what a run leaves there (run.lock, account-maker.log, what failed checks left). An
    # instance serves one run at a time (ins.lock_instance), so no two runs write one file at once, and two
    # checkouts that run suites side by side use instances of their own. Weighed against it: the checkout, where
    # run.py writes nothing today, and the user's cache, which every checkout and session would share. Every
    # instance of a run keeps the times of all its checks, wherever each ran, so that a run on fewer of them, as the
    # windowed suite on 4 after the headless one on 7, knows every check; and as each instance's file is as recent as
    # the last run it served, a check's time is the one written last. A failed check's time is kept too: like any
    # time, it changes only when the check starts.
    latest: t.Dict[str, t.Dict[str, float]] = {}
    instance: ins.Instance
    for instance in instances:
        path: pl.Path = instance.run_dir / "checks" / SECONDS_TAKEN
        if not path.exists():
            continue
        name: str
        taken: t.Dict[str, float]
        for name, taken in json.loads(path.read_text()).items():
            if name not in latest or taken["written"] > latest[name]["written"]:
                latest[name] = taken
    return {name: taken["seconds"] for name, taken in latest.items()}


def write_seconds_taken(instance: ins.Instance, outcomes: t.Sequence[Outcome]) -> None:
    """Keeps in the instance how long each check of the run took, wherever it ran, with what earlier runs kept of
    the others."""
    path: pl.Path = instance.run_dir / "checks" / SECONDS_TAKEN
    kept: t.Dict[str, t.Dict[str, float]] = (
        json.loads(path.read_text()) if path.exists() else {}
    )
    written: float = time.time()
    outcome: Outcome
    for outcome in outcomes:
        kept[outcome.name] = {"seconds": outcome.seconds, "written": written}
    # a run killed while it writes leaves the file of the run before, whole
    new: pl.Path = path.with_name(f"{SECONDS_TAKEN}.new")
    new.write_text(json.dumps(kept, indent=1, sort_keys=True))
    new.replace(path)


def order_longest_first(
    names: t.Sequence[str], seconds_taken: t.Dict[str, float]
) -> t.List[str]:
    """The checks that took longest start first, so that the short ones fill the places that free up and no long
    check waits for a place at the end of a run. A check that has not run yet starts before them all, its time
    unknown. run_checks_at_once deals the checks out to the instances in turn, so each gets its share of long ones."""
    return sorted(names, key=lambda name: -seconds_taken.get(name, math.inf))


def run_checks_at_once(
    names: t.Sequence[str],
    instances: t.Sequence[ins.Instance],
    is_real_window: bool,
    at_once: int,
) -> t.List[Outcome]:
    """Runs the checks, `at_once` of them on each instance at a time, and prints each as it ends."""
    outcomes: t.List[Outcome] = []
    pools: t.List[concurrent.futures.ProcessPoolExecutor] = [
        concurrent.futures.ProcessPoolExecutor(
            max_workers=at_once,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=skip_garbage_collection_at_exit,
        )
        for _ in instances
    ]
    try:
        running: t.List[concurrent.futures.Future[Outcome]] = [
            pools[index % len(pools)].submit(
                run_check, name, instances[index % len(pools)], is_real_window
            )
            for index, name in enumerate(names)
        ]
        future: concurrent.futures.Future[Outcome]
        for future in concurrent.futures.as_completed(running):
            outcomes.append(future.result())
            print_outcome(outcomes[-1])
    finally:
        # the pools are shut down side by side, each waiting for its own processes to end
        stopping: concurrent.futures.ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(len(pools)) as stopping:
            list(stopping.map(lambda pool: pool.shutdown(cancel_futures=True), pools))
    return outcomes


class Command(abc.ABC):
    @abc.abstractmethod
    def run(self) -> int: ...


@dc.dataclass(frozen=True)
class ListChecks(Command):
    names: t.List[str]

    def run(self) -> int:
        name: str
        for name in find_checks(self.names):
            module: types.ModuleType = load_check(name)
            print(f"{name}\n    {get_rule(module)}")
        return 0


@dc.dataclass(frozen=True)
class RunChecks(Command):
    run_dirs: t.List[pl.Path]
    names: t.List[str]
    is_real_window: bool
    at_once: int

    def run(self) -> int:
        if not run_scope.is_in_run_scope():
            run_scope.run_again_in_run_scope()
        run_scope.kill_run_scope_when_this_process_ends()
        start: float = time.monotonic()
        names: t.List[str] = find_checks(self.names)
        locks: t.List[t.TextIO] = [
            ins.lock_instance(run_dir) for run_dir in self.run_dirs
        ]
        # the instances are opened at once: each waits mostly for its own API container
        opening: concurrent.futures.ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(len(self.run_dirs)) as opening:
            instances: t.List[ins.Instance] = list(
                opening.map(ins.open_instance, self.run_dirs)
            )
        outcomes: t.List[Outcome] = run_checks_at_once(
            order_longest_first(names, read_seconds_taken(instances)),
            instances,
            self.is_real_window,
            self.at_once,
        )
        instance: ins.Instance
        for instance in instances:
            write_seconds_taken(instance, outcomes)
        failed: t.List[Outcome] = [
            outcome
            for outcome in outcomes
            if any(step.failure is not None for step in outcome.steps)
        ]
        # the workspace of an instance on which a check failed is kept with what that check left
        instances_to_close: t.List[ins.Instance] = [
            instance
            for instance in instances
            if all(outcome.run_dir != instance.run_dir for outcome in failed)
        ]
        # and the others are closed at once, as they were opened
        closing: concurrent.futures.ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(len(self.run_dirs)) as closing:
            list(closing.map(ins.close_instance, instances_to_close))
        ins.stop_account_makers()
        print(
            f"{len(outcomes)} checks, {sum(len(o.steps) for o in outcomes)} steps, "
            f"{time.monotonic() - start:.0f} s; "
            f"failed: {', '.join(sorted(outcome.name for outcome in failed)) or 'none'}"
        )
        lock: t.TextIO
        for lock in locks:
            lock.close()
        return 1 if failed else 0


def parse_arguments(arguments: t.List[str]) -> Command:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--run-dir",
        type=pl.Path,
        action="append",
        default=[],
        help="directory of a running instance; give it again for each further instance",
    )
    parser.add_argument(
        "--windows",
        action="store_true",
        help="real Chrome windows that nobody sees, in place of headless browsers",
    )
    parser.add_argument(
        "--at-once",
        type=int,
        default=4,
        help="how many checks run at once on each instance",
    )
    parser.add_argument(
        "--list", action="store_true", help="print the checks and their rules; run none"
    )
    parser.add_argument("names", nargs="*", help="checks or groups; all when none")
    parsed: argparse.Namespace = parser.parse_args(arguments)
    if parsed.list:
        return ListChecks(parsed.names)
    if not parsed.run_dir:
        parser.error("--run-dir is needed to run checks")
    return RunChecks(parsed.run_dir, parsed.names, parsed.windows, parsed.at_once)


if __name__ == "__main__":
    sys.exit(parse_arguments(sys.argv[1:]).run())
