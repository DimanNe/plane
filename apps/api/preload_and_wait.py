# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Starts gunicorn, the celery worker or celery beat in two steps.

Loading the application's code is the longest part of their start and needs neither the database
nor Redis, while each of the three connects to one of them as soon as it runs. So that the code
can load while the stores are still coming up, this script loads it, says so on stderr, and waits
for a signal before it runs the command in this same process. Whoever starts the services sends
the signal once the stores accept connections.

usage: python preload_and_wait.py COMMAND [ARGUMENT...]
"""

import gc
import runpy
import signal
import sys

# The signal nothing else in these processes uses and whose default action is to do nothing, so
# sending it again to a service that already runs has no effect.
START_SIGNAL: signal.Signals = signal.SIGURG


def main() -> None:
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
    sys.argv = sys.argv[1:]
    runpy.run_module(sys.argv[0], run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
