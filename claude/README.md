# claude/

What a Claude session needs to change this fork and to check the change, beyond what the
repository already has. Everything here is used in every round of work. Nothing here records
past work: that is in the commits and in the tracker.

## An instance of your own

Work is tried on an instance that holds nothing that matters, never on one that holds real
tasks. `scripts/plane_runtime.py` makes and runs one (`--help` lists its commands): `prepare
--image-tag TAG` builds the images, `start --run-dir DIR --bind 127.0.0.1:PORT --image-tag TAG`
starts an instance whose data is in `DIR`, `bootstrap-user` gives it an administrator and prints
the API token of that account.

**Images of your own.** An instance runs the images built last under its tag and applies their
migrations to its data. Without `--image-tag` the tag is `current`, the owner's, whose instance
holds the tasks. So a session:

- always passes `--image-tag TAG` to `prepare`, `start` and `import`, with a tag of its own,
  such as its task (`plane-47`). An instance runs only the images of its first start: `start`
  refuses another tag;
- has its own worktree, run directories and ports, so that no session waits for another;
- builds images only for a change that needs it (the API), with `tools/rebuild_and_restart.sh`;
- says so in the task when a round has a migration: the owner's instance gets it when the owner
  builds the delivered code;
- deletes its images when the round is over, after `stop`. The stopped containers of its
  instances still use them, and hold nothing that the run directory (absolute) does not:

      docker rm $(docker ps -aq --filter label=org.plane.local.target=RUN_DIR)
      docker image rm plane-local-{api,live,space,proxy}:TAG

## Seeing a change

| change | tool | takes |
|---|---|---|
| web app | `tools/web_to_instance.sh RUN_DIR` builds the web app of the checkout it is in and copies it into the running instance | about a minute |
| API | `tools/rebuild_and_restart.sh RUN_DIR 127.0.0.1:PORT TAG` | several minutes |

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
- `claude/checks/run.py --run-dir RUN_DIR`, and once more with `--windows`: the rules that earlier
  tasks settled still hold. See "Checks" below.
- In a browser on your instance, with real clicks, drags, wheel and key presses (Playwright),
  reading back through `/api/v1/` what should have been stored. What is judged by eye is looked
  at in enlarged screenshots, in the light and the dark theme. When an animation looks wrong,
  sample the geometry frame by frame before reading code.
- What moves on the page is also tried in a real Chrome window started with the flags of the
  owner's Chrome, which `tools/offscreen_chrome.py PORT PROFILE_DIR FLAGS...` runs unseen. A
  headless browser draws differently: a transition that ended there never ended in his window.
- Typing in the list, opening a pop-up and dragging on the timeline were made fast by measuring.
  A change near them is measured again, before and after, with `claude/checks/measure.py --run-dir RUN_DIR`.
- A step that depends on time can fail only because another session has the processors. Run it
  again before concluding anything, and write the machine's load beside a time you measure.

## Checks

`claude/checks/` holds what earlier tasks settled about the web app, one file for each rule;
`checks/run.py --list` prints them with their rules, and `--help` says how to run some of them.
A run needs running instances and nothing else: it makes an account and a project for every
check, spreads the checks over the run directories it is given, and removes what passed.

A check says in its first lines the rule it guards. Then it reads from top to bottom: the data it
builds through `/api/v1/`, what a person does, with real pointer and key events, and what must
then be true on the page and on the server. A step waits for what the page shows and never by
the clock, unless its rule is about time, such as a key repeat. It reads again when the page has
changed (`page_changes.py`): `wait_until_shown`, `wait_until_removed` and `wait_until_true` take
the place of Playwright's `wait_for` and `wait_for_function`, which read again on a clock or every
frame. What two checks need is in the modules beside `run.py`.

**A task that changes behaviour changes its check in the same commit**, and a task that settles
a new rule adds a check for it.

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
- Nothing that the task does not ask for: no option, setting or convenience, and no guard for a
  state that nothing can produce.
- The web app follows upstream: data in MobX stores read through hooks, the primitives of
  `@plane/propel`, `@plane/ui` and `@plane/blocks`, the licence header on a new file. A new text
  gets its key in the English locale only.
- A comment says what the code cannot: why a thing exists. It does not retell the code and holds
  no value that the next change makes false.
- A unit test is a table of named cases that compares whole results, is named for the rule it
  checks, and can fail.
- Plain English and the words Plane already uses, in code, texts and commit messages. Never
  "pin", "gate", "lag", "load-bearing", "rides"; "row" only for a row of the list, of a table or
  of the database.
- The names and texts of the tasks in the owner's tracker stay in the tracker. Tests, comments
  and commit messages use invented names.
- No View Transition of the browser (`document.startViewTransition`). The owner's Chrome runs
  with `--disable-frame-rate-limit`, where such a transition never ends; CSS transitions and
  Web Animations do.
