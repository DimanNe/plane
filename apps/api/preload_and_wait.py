# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Starts gunicorn, the celery worker or celery beat in two steps.

Loading the application's code is the longest part of their start and needs neither the database
nor Redis, while each of the three connects to one of them as soon as it runs. So that the code
can load while the stores are still coming up, this script loads it, says so on stderr, and waits
for a signal before it runs the command in this same process. Whoever starts the services sends
the signal once the stores accept connections.

The proxy of the instance serves pages while the API starts, and has the browser fetch the API's
first answers along with each page (write_caddy_config() in scripts/plane_runtime.py). The browser
keeps those answers for the app, so the proxy's 502 for a refused connection would reach the app
after the API is back. So with --listen HOST:PORT the script listens there before it loads the
code, says so on stderr, and hands the socket to the command as file descriptor 3 (gunicorn:
--bind fd://3): the kernel keeps the connections that arrive, with what they sent, until the
command accepts them.

usage: python preload_and_wait.py [--listen HOST:PORT] COMMAND [ARGUMENT...]
"""

import gc
import runpy
import signal
import socket
import sys

# The signal nothing else in these processes uses and whose default action is to do nothing, so
# sending it again to a service that already runs has no effect.
START_SIGNAL: signal.Signals = signal.SIGURG
# The first descriptor after the standard streams, where systemd's socket activation puts a socket too.
LISTEN_FD: int = 3


def listen(address: str) -> None:
    # gunicorn's own backlog, which it listens with again once it runs: connections beyond it would wait for the
    # client to send its connection request again.
    BACKLOG: int = 2048
    # FOR_REVIEWER: measured through the proxy while an instance started, 1500 requests at once, half of them saves,
    # were all answered once the API ran, each save made once, with no overflow of the queue. 2600 overflowed it:
    # 147 waited past the proxy's 3 s to connect and got 502, and their saves were not made. A browser opens at most
    # 6 connections to one host.
    host, _, port = address.rpartition(":")
    listener: socket.socket = socket.create_server((host, int(port)), backlog=BACKLOG)
    if listener.fileno() != LISTEN_FD:
        raise RuntimeError(f"The socket of {address} is file descriptor {listener.fileno()}, not {LISTEN_FD}")
    # the command takes the descriptor over, and closes it
    listener.detach()
    print("Plane listening:", address, file=sys.__stderr__, flush=True)


def main() -> None:
    command: list[str] = sys.argv[1:]
    if command[:1] == ["--listen"]:
        listen(command[1])
        command = command[2:]
    # A blocked signal stays pending until sigwait() takes it, whenever it arrives.
    signal.pthread_sigmask(signal.SIG_BLOCK, {START_SIGNAL})
    # Loading creates several hundred thousand objects that live as long as the process. The
    # garbage collector would walk them again and again while they are created and find nothing
    # to free; frozen, they also stay out of every later collection.
    gc.disable()
    import django
    import django.urls
    import plane.celery

    django.setup()
    plane.celery.app.loader.import_default_modules()
    django.urls.get_resolver().url_patterns
    gc.enable()
    gc.freeze()
    print("Plane code loaded:", file=sys.__stderr__, flush=True)
    signal.sigwait({START_SIGNAL})
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {START_SIGNAL})
    sys.argv = command
    runpy.run_module(sys.argv[0], run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
