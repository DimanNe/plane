# claude/

What a Claude session needs to change this fork and to check the change, beyond what the
repository already has. Everything here is used in every round of work. Nothing here records
past work: that is in the commits and in the tracker.

## An instance of your own

Work is tried on an instance that holds nothing that matters, never on one that holds real
tasks. `scripts/plane_runtime.py` makes and runs one (`--help` lists its commands): `prepare`
builds the images, `start --run-dir DIR --port PORT` starts an instance whose data is in `DIR`,
`bootstrap-user` gives it an administrator and prints the API token of that account.

**The image names are the same for every instance on the machine.** An instance that is started
later, by anybody, runs the images that were built last and applies their migrations to its
data. Therefore:

- build images only for a change that needs it (the API), with `tools/rebuild_and_restart.sh`,
  which builds and restarts your instance as one step under a lock;
- do not build while the owner may be starting the instance that holds his tasks, and say so
  before a round that has a migration;
- when the round is over, build the images from the delivered code again.

## Seeing a change

| change | tool | takes |
|---|---|---|
| web app | `tools/web_to_instance.sh RUN_DIR` builds the web app of the checkout it is in and copies it into the running instance | about a minute |
| API | `tools/rebuild_and_restart.sh RUN_DIR PORT` | several minutes |

## Before a change is handed over

- `pnpm turbo run build --filter='./packages/*'` and `pnpm --filter web run check:types`.
- `pnpm exec vitest run` in `packages/blocks`, the one package that has unit tests. Logic that
  deserves tests (the timeline's scheduling, for one) is put there for that reason.
- `pnpm exec oxlint` and `pnpm exec oxfmt --check` on the changed files. Upstream files have
  warnings of their own: compare with the base, add none.
- The API's tests against the stores of your instance, and the migration check:

      claude/tools/api_env.py --run-dir RUN_DIR --port PORT --venv VENV --db-name plane_checks --redis-db 6 -- \
          python -m pytest -q -p no:cacheprovider -o addopts="--strict-markers --create-db --nomigrations" plane/tests
      claude/tools/api_env.py ... -- python manage.py makemigrations --check --dry-run

  `VENV` is a Python environment with the packages of `apps/api`. `ruff check` and
  `ruff format --check` on the fork's own Python files; upstream's are not all formatted.
- In a browser on your instance, with real clicks, drags, wheel and key presses (Playwright),
  reading back through `/api/v1/` what should have been stored. What is judged by eye is looked
  at in enlarged screenshots, in the light and the dark theme. When an animation looks wrong,
  sample the geometry frame by frame before reading code.
- Typing in the list, opening a pop-up and dragging on the timeline were made fast by measuring.
  A change near them is measured again, before and after.

## Tasks

Tasks are in the Plane tracker, in the project of this repository. `tools/tracker.py` lists
them, shows one, and sets states and comments, for a session without the tracker's MCP tools.

- Work on a task starts when the owner names it or its state; a task that only appears in the
  tracker is not yet a request.
- Questions go to the owner before anything is built, with a recommendation. Where the task
  leaves room and no question is worth his time, the decision is taken and told to him.
- A task goes to In Progress when work on it starts, and to Review when its commit is in the
  repository, with a comment that says what he now sees, the commit, and what he may want
  changed.
- One commit per task. The subject ends with the task's id, `(PLANE-7)`. The message says the
  problem that is solved, not how. Nothing is pushed.

## How changes are made here

- Upstream files get the smallest diff that does the job: no reformatting, no renames, no moved
  lines. New code goes into new files.
- No new dependency, service, environment variable or flag without a word from the owner.
- One rule lives in one place (the timeline's rules in `packages/blocks/src/timeline-schedule`;
  the server does no scheduling).
- The fork's own Python is written like `scripts/plane_runtime.py`; upstream's files keep
  upstream's style. Texts of the interface go through i18n.
- A failure says what failed and why. No retry machinery.
