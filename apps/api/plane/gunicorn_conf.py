import sys

import gunicorn.workers.base as gunicorn_workers


def post_worker_init(worker: gunicorn_workers.Worker) -> None:
    print(f"Plane API worker ready: {worker.pid}", file=sys.__stderr__, flush=True)
