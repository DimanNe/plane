"""
Nothing of a run of the checks outlives it.

A run starts processes for its checks, and each of those starts the Playwright driver, a browser and, for a real
window, a compositor in a session of its own. A run that is killed, or that dies, cannot stop them, and they wait
for it for ever. Linux kills every process of a control group at once (cgroup v2, cgroup.kill), so a run holds
them all in a control group that is its own and nobody else's: a scope of the user's systemd that is made for
this run alone and handed to the user (Delegate=yes), the run scope. A process of its own kills the run scope
when the run has ended.

The run scope is known by its name, which holds the number of the run's process. Whether a group can be killed
says nothing about whose it is: root can kill every group, and a delegated group, such as that of a terminal
multiplexer, holds other processes too.
"""

import os
import pathlib as pl
import signal
import sys
import typing as t

CGROUP_ROOT: pl.Path = pl.Path("/sys/fs/cgroup")
RUN_SCOPE_NAME_START: str = "checks-run-scope-"


def get_own_cgroup() -> pl.Path:
    # with cgroup v2 alone the file has one line: 0::PATH
    path: str = pl.Path("/proc/self/cgroup").read_text().split(":", 2)[2].strip()
    return CGROUP_ROOT / path.lstrip("/")


def get_run_scope_name() -> str:
    return f"{RUN_SCOPE_NAME_START}{os.getpid()}"


def is_in_run_scope() -> bool:
    return get_own_cgroup().name == f"{get_run_scope_name()}.scope"


def run_again_in_run_scope() -> t.NoReturn:
    """Starts this command again in the run scope; returns never. The command keeps this process, and with it
    the number in the scope's name."""
    # systemd-run finds the user's systemd by this directory, which a session without a login manager has not set
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    command: t.List[str] = [
        "systemd-run",
        "--user",
        "--scope",
        f"--unit={get_run_scope_name()}",
        "--quiet",
        "--collect",
        "--property=Delegate=yes",
        "--",
        sys.executable,
        *sys.argv,
    ]
    os.execvp(command[0], command)


def kill_run_scope_when_this_process_ends() -> None:
    """Starts a process that waits for the end of this one, however it comes, and then kills whatever is left in
    the run scope, itself included."""
    if not is_in_run_scope():
        raise RuntimeError(f"Not in the run scope: {get_own_cgroup()}")
    run_scope: pl.Path = get_own_cgroup()
    read_end: int
    write_end: int
    read_end, write_end = os.pipe()
    if os.fork() != 0:
        # The kernel closes this end when the process ends, whatever ends it. Nothing else holds it: the pipe is
        # not inherited by the processes this one starts.
        os.close(read_end)
        return
    os.close(write_end)
    # Ctrl+C and a signal to the process group are meant for the run; they end it, and so this process's wait.
    ignored: signal.Signals
    for ignored in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(ignored, signal.SIG_IGN)
    os.read(read_end, 1)
    (run_scope / "cgroup.kill").write_text("1")
    os._exit(0)
