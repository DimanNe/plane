import sys

import gunicorn.workers.base as gunicorn_workers

import plane.db.change_notifications as change_notifications


def post_worker_init(worker: gunicorn_workers.Worker) -> None:
    change_notifications.start_relay()
    print(f"Plane API worker ready: {worker.pid}", file=sys.__stderr__, flush=True)
