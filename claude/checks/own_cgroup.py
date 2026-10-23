"""
Nothing of a run of the checks outlives it.

A run starts processes for its checks, and each of those starts the Playwright driver, a browser and, for a real
window, a compositor in a session of its own. A run that is killed, or that dies, cannot stop them, and they wait
for it for ever. Linux kills every process of a control group at once (cgroup v2, cgroup.kill), but only the
owner of the group may: the group of a login session belongs to root. So a run starts itself again in a scope
of the user's systemd that is handed to the user (Delegate=yes), which every process of the run inherits, and a
process of its own kills that scope when the run has ended.
"""

import os
import pathlib as pl
import signal
import sys
import typing as t

CGROUP_ROOT: pl.Path = pl.Path("/sys/fs/cgroup")


def get_own_cgroup() -> pl.Path:
    # with cgroup v2 alone the file has one line: 0::PATH
    path: str = pl.Path("/proc/self/cgroup").read_text().split(":", 2)[2].strip()
    return CGROUP_ROOT / path.lstrip("/")


def can_kill_own_cgroup() -> bool:
    return os.access(get_own_cgroup() / "cgroup.kill", os.W_OK)


def run_again_in_own_cgroup() -> t.NoReturn:
    """Starts this command again, in this process, in a new scope of the user's systemd; returns never."""
    # systemd-run finds the user's systemd by this directory, which a session without a login manager has not set
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    command: t.List[str] = [
        "systemd-run",
        "--user",
        "--scope",
        "--quiet",
        "--collect",
        "--property=Delegate=yes",
        "--",
        sys.executable,
        *sys.argv,
    ]
    os.execvp(command[0], command)


def kill_own_cgroup_when_this_process_ends() -> None:
    """Starts a process that waits for the end of this one, however it comes, and then kills whatever is left in
    their control group, itself included."""
    cgroup: pl.Path = get_own_cgroup()
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
    (cgroup / "cgroup.kill").write_text("1")
    os._exit(0)
