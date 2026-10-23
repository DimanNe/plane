"""
A running instance as the checks use it: its address, the accounts of one run, and its two APIs.

Nothing about an instance is written down anywhere. Its address is what the runtime published for the run
directory. A run signs in as an administrator of its own, makes a workspace for itself, and in it an account
and a project for every check, so that two checks never share anything that can change.

Data is built and read back through /api/v1/ with the administrator's token. What only the web app's own API
does (members, the display of a list) is done as the account it belongs to, with that account's session.
"""

import concurrent.futures
import dataclasses as dc
import fcntl
import http.client
import json
import os
import pathlib as pl
import secrets
import socket
import socketserver
import string
import subprocess
import sys
import textwrap
import threading
import time
import typing as t
import urllib.parse

REPOSITORY: pl.Path = pl.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "scripts"))

import plane_config  # noqa: E402
import plane_runtime  # noqa: E402

JSONObject: t.TypeAlias = t.Dict[str, t.Any]

# Run by the API's own Python once per instance and run, and kept running until the run ends, it makes the run's
# administrator as it starts (see plane_runtime.BOOTSTRAP_ADMINISTRATOR) and then the run's other accounts. Made by a process of its own, an account took about 0.8 s, of which the database was about 0.06 s: the
# process loaded all of Plane (django.setup) and exited again, and hashed the password with the hash Django keeps
# passwords with, which is slow on purpose. Here Plane is loaded once, and the password, the same for every account
# of the run, is hashed once. It answers each request, a line of JSON, with a line of JSON, as soon as it is made.
# The server limits what one address may do in a minute while it is not signed in, and a run does more:
# - the form of the sign-in page lets an address in a few times, and a run has more accounts than that; so an
#   account is signed in where the server keeps its sessions, the way Django's test client does it;
# - a page asks first what instance this is, a question the server answers so many times, since it reads the
#   session for it from the cookie of its admin pages, which a user does not have; without the answer the page
#   says that Plane did not start. So the account's session goes under that cookie's name too.
# The account is also past the pages of a first visit.
ACCOUNT_MAKER: str = (
    textwrap.dedent("""\
    import concurrent.futures
    import importlib
    import json
    import sys
    import threading
    import django
    django.setup()
    import django.conf as conf
    import django.contrib.auth as auth
    import django.contrib.auth.hashers as hashers
    import django.http as http
    import plane.db.models as db_models
""")
    + plane_runtime.BOOTSTRAP_ADMINISTRATOR
    + textwrap.dedent("""\
    password_hash: str = hashers.make_password(sys.argv[1])
    administrator: dict = bootstrap_administrator(sys.argv[2], password_hash)
    printing: threading.Lock = threading.Lock()


    def sign_in(email: str) -> dict:
        user, _ = db_models.User.objects.get_or_create(email=email, defaults={"username": email})
        user.password = password_hash
        user.is_password_autoset = False
        user.save()
        seen: dict = dict.fromkeys(db_models.Profile(user=user).onboarding_step, True)
        db_models.Profile.objects.update_or_create(
            user=user, defaults={"is_onboarded": True, "is_tour_completed": True, "onboarding_step": seen}
        )
        request = http.HttpRequest()
        request.session = importlib.import_module(conf.settings.SESSION_ENGINE).SessionStore()
        auth.login(request, user, backend=conf.settings.AUTHENTICATION_BACKENDS[0])
        request.session.save()
        cookies: dict = dict.fromkeys(
            (conf.settings.SESSION_COOKIE_NAME, conf.settings.ADMIN_SESSION_COOKIE_NAME), request.session.session_key
        )
        return {"user_id": str(user.id), "cookies": cookies}


    def answer(request: dict) -> None:
        try:
            reply: dict = {"id": request["id"], **sign_in(request["email"])}
        except Exception as error:
            reply = {"id": request["id"], "error": repr(error)}
        with printing:
            print(json.dumps(reply), flush=True)


    print(json.dumps({"ready": True, "api_key": administrator["api_key"]}), flush=True)
    # several at once, since a run's checks start together and each asks for its accounts first
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for line in sys.stdin:
            pool.submit(answer, json.loads(line))
""")
)

# Every run on an instance signs in as this administrator, with a password it draws anew: the workspaces that
# earlier runs left belong to it, so the next run can remove them.
ADMINISTRATOR_EMAIL: str = "checks@plane.invalid"
WORKSPACE_PREFIX: str = "checks-"
ROLE_ADMIN: int = 20
ROLE_MEMBER: int = 15
ROLE_GUEST: int = 5
# an id of the form the server gives, which it has given to nothing
NO_SUCH_ID: str = "00000000-0000-4000-8000-000000000000"


@dc.dataclass(frozen=True)
class Account:
    email: str
    password: str
    user_id: str
    cookies: t.Dict[str, str] = dc.field(compare=False)


@dc.dataclass(frozen=True)
class Instance:
    url: str
    run_dir: pl.Path
    api_key: str
    administrator: Account
    workspace: str
    # where the run's account maker of this instance takes requests (see AccountMaker)
    account_maker_address: str
    # the password of every account of the run, the administrator's too
    password_of_accounts: str


@dc.dataclass(frozen=True)
class Project:
    id: str
    identifier: str
    name: str
    states: t.Dict[str, str]


def draw_name(length: int) -> str:
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(length))


# The connection of this process to each address, kept for its next call. Rootless Docker's network namespace
# tracks every connection to a published port and keeps the entry for a while after the connection has closed; on a
# machine started with little memory, its table holds a few thousand. A connection for every call filled it, and new
# connections to every published port, those of other instances too, were dropped until it drained: a call waited
# up to a minute.
CONNECTIONS: t.Dict[str, http.client.HTTPConnection] = {}


def send(
    url: str, method: str, headers: t.Dict[str, str], body: t.Optional[bytes]
) -> t.Any:
    parts: urllib.parse.SplitResult = urllib.parse.urlsplit(url)
    if parts.netloc not in CONNECTIONS:
        CONNECTIONS[parts.netloc] = http.client.HTTPConnection(parts.netloc, timeout=60)
    connection: http.client.HTTPConnection = CONNECTIONS[parts.netloc]
    try:
        connection.request(
            method,
            parts.path + (f"?{parts.query}" if parts.query else ""),
            body,
            headers,
        )
        response: http.client.HTTPResponse = connection.getresponse()
        text: str = response.read().decode()
    except Exception:
        # a call that broke off leaves the connection unusable; the next call opens another one
        connection.close()
        raise
    if not 200 <= response.status < 300:
        raise RuntimeError(
            f"{method} {url} was answered {response.status}: {text[:400]}"
        )
    return json.loads(text) if text[:1] in ("{", "[") else text


def call_api(
    instance: Instance, method: str, path: str, body: t.Optional[JSONObject] = None
) -> t.Any:
    """A call of /api/v1/ in the run's workspace, as its administrator."""
    return send(
        f"{instance.url}/api/v1/workspaces/{instance.workspace}{path}",
        method,
        {"X-Api-Key": instance.api_key, "Content-Type": "application/json"},
        None if body is None else json.dumps(body).encode(),
    )


def call_app(
    url: str,
    account: Account,
    method: str,
    path: str,
    body: t.Optional[JSONObject] = None,
) -> t.Any:
    """A call of the web app's own API, as a signed-in account."""
    cookie: str = "; ".join(
        f"{name}={value}" for name, value in account.cookies.items()
    )
    return send(
        f"{url}/api{path}",
        method,
        {"Cookie": cookie, "Content-Type": "application/json"},
        None if body is None else json.dumps(body).encode(),
    )


class AccountMaker:
    """The run's account maker of one instance (see ACCOUNT_MAKER), and the socket on which the run's checks ask it
    for accounts: they run in processes of their own, while the account maker's input and output belong to the
    run's main process. The socket has an address and no file, and goes with the process."""

    def __init__(self, run_dir: pl.Path, password: str) -> None:
        # FOR_REVIEWER: one account takes about 7 ms here, but its threads share one interpreter lock, so the 54
        # accounts that a run's checks ask for as they start are made one after another: the last waits about
        # 0.4 s. Workers forked after Plane is loaded would make them side by side, at the cost of memory, which is
        # what limits the instances a run can have; not done until that 0.4 s is on the path of the slowest check.
        self.run_dir: pl.Path = run_dir
        self.log: pl.Path = run_dir / "checks" / "account-maker.log"
        self.log.parent.mkdir(exist_ok=True)
        log: t.TextIO
        with self.log.open("w") as log:
            self.process: subprocess.Popen[str] = subprocess.Popen(
                [
                    "docker",
                    "exec",
                    "-i",
                    plane_runtime.get_container_name(run_dir, plane_config.Service.API),
                    "python",
                    "-u",
                    "-c",
                    ACCOUNT_MAKER,
                    password,
                    ADMINISTRATOR_EMAIL,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=log,
                text=True,
            )
        assert self.process.stdin is not None and self.process.stdout is not None
        ready: JSONObject = json.loads(self.process.stdout.readline() or "{}")
        if ready.get("ready") is not True:
            raise RuntimeError(
                f"The account maker of {run_dir} did not start; see {self.log}"
            )
        # the API token of the run's administrator, which the account maker made as it started
        self.administrator_api_key: str = ready["api_key"]
        self.writing: threading.Lock = threading.Lock()
        self.last_id: int = 0
        self.waiting: t.Dict[int, concurrent.futures.Future[JSONObject]] = {}
        threading.Thread(target=self.read_answers, daemon=True).start()
        self.address: str = (
            f"\0plane-checks-account-maker-{os.getpid()}-"
            + plane_runtime.get_container_name_prefix(run_dir)
        )
        account_maker: AccountMaker = self

        class AskForAccount(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                reply: JSONObject = account_maker.ask(
                    json.loads(self.rfile.readline())["email"]
                )
                self.wfile.write(json.dumps(reply).encode() + b"\n")

        self.server: socketserver.ThreadingUnixStreamServer = (
            socketserver.ThreadingUnixStreamServer(self.address, AskForAccount)
        )
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def read_answers(self) -> None:
        assert self.process.stdout is not None
        line: str
        for line in self.process.stdout:
            reply: JSONObject = json.loads(line)
            self.waiting.pop(reply["id"]).set_result(reply)
        # the account maker ended: nothing that is still waiting gets an answer
        with self.writing:
            future: concurrent.futures.Future[JSONObject]
            for future in self.waiting.values():
                future.set_exception(
                    RuntimeError(
                        f"The account maker of {self.run_dir} ended; see {self.log}"
                    )
                )
            self.waiting.clear()

    def ask(self, email: str) -> JSONObject:
        """The account maker's answer for the account with this address: its id and its session, or an error."""
        assert self.process.stdin is not None
        future: concurrent.futures.Future[JSONObject] = concurrent.futures.Future()
        with self.writing:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"The account maker of {self.run_dir} ended; see {self.log}"
                )
            self.last_id += 1
            self.waiting[self.last_id] = future
            self.process.stdin.write(
                json.dumps({"id": self.last_id, "email": email}) + "\n"
            )
            self.process.stdin.flush()
        return future.result()

    def stop(self) -> None:
        assert self.process.stdin is not None
        self.server.shutdown()
        self.server.server_close()
        # at the end of its input the account maker ends
        self.process.stdin.close()
        self.process.wait()


# The account makers this process started, by run directory: only a run's main process has any.
ACCOUNT_MAKERS: t.Dict[pl.Path, AccountMaker] = {}


def read_account(email: str, password: str, reply: JSONObject) -> Account:
    if "error" in reply:
        raise RuntimeError(
            f"The account maker could not sign in {email}: {reply['error']}"
        )
    return Account(email, password, reply["user_id"], reply["cookies"])


def sign_in(instance: Instance, email: str) -> Account:
    """Gives the account with this address a session, and makes the account when there is none: through the run's
    account maker of the instance."""
    connection: socket.socket
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(instance.account_maker_address)
        connection.sendall(json.dumps({"email": email}).encode() + b"\n")
        reply: JSONObject = json.loads(connection.makefile().readline())
    return read_account(email, instance.password_of_accounts, reply)


def find_url(run_dir: pl.Path) -> str:
    network: plane_config.Service = plane_config.Service.NETWORK
    containers: plane_runtime.Containers = plane_runtime.get_containers(
        run_dir, [network]
    )
    if network not in containers or not containers[network]["State"].get("Running"):
        raise SystemExit(f"No running instance in {run_dir}")
    published: str = f"{plane_runtime.SERVICE_PORTS[plane_config.Service.PROXY]}/tcp"
    port: str = containers[network]["HostConfig"]["PortBindings"][published][0][
        "HostPort"
    ]
    return f"http://localhost:{port}"


def remove_workspaces_of_earlier_runs(url: str, administrator: Account) -> None:
    workspace: JSONObject
    for workspace in call_app(url, administrator, "GET", "/users/me/workspaces/"):
        if workspace["slug"].startswith(WORKSPACE_PREFIX):
            call_app(url, administrator, "DELETE", f"/workspaces/{workspace['slug']}/")


def lock_instance(run_dir: pl.Path) -> t.TextIO:
    """Takes the instance for one run of the checks, until the file returned is closed or the run ends. A second
    run would remove the workspace of the first, and both would fail in ways that say nothing; so it ends here."""
    held: pl.Path = plane_runtime.resolve_run_dir(run_dir) / "checks" / "run.lock"
    held.parent.mkdir(exist_ok=True)
    lock: t.TextIO = open(held, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(
            f"A run of the checks is using the instance in {run_dir}"
        ) from None
    return lock


def wait_until_workspace_seeded(
    url: str, administrator: Account, workspace: str
) -> None:
    """Plane seeds a new workspace in the background (workspace_seed) with a sample project, whose members are the
    members of the workspace when the seeding begins. The run's accounts must join after that moment, or their
    pages show a project that no check made; the sample project shows that the moment has passed. Accounts that
    took a second each to make always joined later; made in milliseconds, they would join first."""
    # there is no event to wait on from outside the server: its state is read again until it shows the project
    deadline: float = time.monotonic() + 60
    while not call_app(url, administrator, "GET", f"/workspaces/{workspace}/projects/"):
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Plane did not seed the workspace {workspace}: does the instance's worker (celery) run?"
            )
        time.sleep(0.02)


def open_instance(run_dir: pl.Path) -> Instance:
    """Makes the instance ready for one run: its administrator, and an empty workspace of the run's own."""
    run_dir = plane_runtime.resolve_run_dir(run_dir)
    url: str = find_url(run_dir)
    # FOR_REVIEWER: every account of a run, the administrator too, has this one password and so one hash, salt
    # included, which is why it is hashed once. They are accounts of a run that hold nothing; a check that signs
    # in through the form (addresses/sign_in) types this password.
    password: str = secrets.token_urlsafe(16)
    account_maker: AccountMaker = AccountMaker(run_dir, password)
    ACCOUNT_MAKERS[run_dir] = account_maker
    administrator: Account = read_account(
        ADMINISTRATOR_EMAIL, password, account_maker.ask(ADMINISTRATOR_EMAIL)
    )
    remove_workspaces_of_earlier_runs(url, administrator)
    workspace: str = WORKSPACE_PREFIX + draw_name(8)
    call_app(
        url,
        administrator,
        "POST",
        "/workspaces/",
        {"name": "Checks", "slug": workspace, "organization_size": "1"},
    )
    wait_until_workspace_seeded(url, administrator, workspace)
    return Instance(
        url,
        run_dir,
        account_maker.administrator_api_key,
        administrator,
        workspace,
        account_maker.address,
        password,
    )


def stop_account_makers() -> None:
    account_maker: AccountMaker
    for account_maker in ACCOUNT_MAKERS.values():
        account_maker.stop()
    ACCOUNT_MAKERS.clear()


def close_instance(instance: Instance) -> None:
    call_app(
        instance.url,
        instance.administrator,
        "DELETE",
        f"/workspaces/{instance.workspace}/",
    )


def make_account(instance: Instance, role: int = ROLE_ADMIN) -> Account:
    """A new account that is a member of the run's workspace."""
    account: Account = sign_in(instance, f"{draw_name(12)}@plane.invalid")
    invitations: str = f"/workspaces/{instance.workspace}/invitations/"
    call_app(
        instance.url,
        instance.administrator,
        "POST",
        invitations,
        {"emails": [{"email": account.email, "role": role}]},
    )
    invitation: JSONObject
    for invitation in call_app(
        instance.url, account, "GET", "/users/me/workspaces/invitations/"
    ):
        call_app(
            instance.url,
            account,
            "POST",
            "/users/me/workspaces/invitations/",
            {"invitations": [invitation["id"]]},
        )
    return account


def make_project(
    instance: Instance, members: t.Dict[Account, int], **fields: t.Any
) -> Project:
    """A new project of the run's workspace with these members and their roles."""
    identifier: str = draw_name(6).upper()
    created: JSONObject = call_api(
        instance,
        "POST",
        "/projects/",
        {"name": f"Project {identifier}", "identifier": identifier, **fields},
    )
    account: Account
    role: int
    for account, role in members.items():
        call_app(
            instance.url,
            instance.administrator,
            "POST",
            f"/workspaces/{instance.workspace}/projects/{created['id']}/members/",
            {"members": [{"member_id": account.user_id, "role": role}]},
        )
    states: t.List[JSONObject] = call_api(
        instance, "GET", f"/projects/{created['id']}/states/"
    )["results"]
    return Project(
        created["id"],
        created["identifier"],
        created["name"],
        {state["name"]: state["id"] for state in states},
    )


def make_state(instance: Instance, project: Project, name: str, group: str) -> Project:
    """A further state of the project, in one of the groups a state can have; returns the project with it."""
    state: JSONObject = call_api(
        instance,
        "POST",
        f"/projects/{project.id}/states/",
        {"name": name, "group": group, "color": "#8b5cf6"},
    )
    return dc.replace(project, states={**project.states, name: state["id"]})


def remove_project(instance: Instance, project: Project) -> None:
    call_api(instance, "DELETE", f"/projects/{project.id}/")


def set_display(
    instance: Instance,
    account: Account,
    project: Project,
    of_list: str = "",
    **display_filters: t.Any,
) -> None:
    """The account's choices under Display for the project, as the page keeps them on the server. `of_list` is the
    cycle or the module whose list has choices of its own, such as `cycles/ID/`."""
    path: str = f"/workspaces/{instance.workspace}/projects/{project.id}/{of_list}user-properties/"
    kept: JSONObject = call_app(instance.url, account, "GET", path)
    call_app(
        instance.url,
        account,
        "PATCH",
        path,
        {
            "display_filters": {**kept["display_filters"], **display_filters},
            "rich_filters": {},
        },
    )


def make_work_items(
    instance: Instance, project: Project, items: t.Sequence[JSONObject]
) -> t.Dict[str, str]:
    """
    Work items in the order given, which is also their manual order. Each is the fields of /api/v1/, but for
    two that are given by name: `state`, and `parent`, a work item earlier in the list. Returns their ids by name.
    """
    ids: t.Dict[str, str] = {}
    item: JSONObject
    for item in items:
        fields: JSONObject = dict(item)
        if "state" in fields:
            fields["state"] = project.states[fields["state"]]
        if "parent" in fields:
            fields["parent"] = ids[fields["parent"]]
        ids[item["name"]] = call_api(
            instance, "POST", f"/projects/{project.id}/work-items/", fields
        )["id"]
    return ids


# A work item keeps the moment it was completed or cancelled (completed_at, cancelled_at) as it happens, and
# /api/v1/ cannot set it; run by the API's own Python, this moves that moment back for the work items given.
MOVE_CLOSING_BACK: str = textwrap.dedent("""\
    import datetime
    import json
    import sys
    import django
    django.setup()
    import django.utils.timezone as timezone
    import plane.db.models as db_models
    closed_at = timezone.now() - datetime.timedelta(days=float(sys.argv[2]))
    issues = db_models.Issue.objects.filter(id__in=json.loads(sys.argv[1]))
    issues.filter(completed_at__isnull=False).update(completed_at=closed_at)
    issues.filter(cancelled_at__isnull=False).update(cancelled_at=closed_at)
""")


def move_closing_back(
    instance: Instance, work_item_ids: t.Sequence[str], days: float
) -> None:
    """Makes the closed work items given look as if they were completed or cancelled `days` ago."""
    plane_runtime.run_docker(
        [
            "exec",
            plane_runtime.get_container_name(
                instance.run_dir, plane_config.Service.API
            ),
            "python",
            "-c",
            MOVE_CLOSING_BACK,
            json.dumps(list(work_item_ids)),
            str(days),
        ],
        capture=True,
    )


def read_work_items(instance: Instance, project: Project) -> t.Dict[str, JSONObject]:
    """Every work item the project has stored, by name."""
    found: t.Dict[str, JSONObject] = {}
    path: str = f"/projects/{project.id}/work-items/?per_page=100"
    cursor: str = ""
    while True:
        page: JSONObject = call_api(instance, "GET", path + cursor)
        found.update({item["name"]: item for item in page["results"]})
        if not page["next_page_results"]:
            return found
        cursor = f"&cursor={page['next_cursor']}"


def read_work_item_names(instance: Instance, project: Project) -> t.List[str]:
    """The names of the work items the project has stored, in order."""
    return sorted(read_work_items(instance, project))


def read_state_name(instance: Instance, project: Project, name: str) -> str:
    """The name of the state the server has stored for the work item called `name`."""
    states: t.Dict[str, str] = {
        state_id: state for state, state_id in project.states.items()
    }
    return states[read_work_items(instance, project)[name]["state"]]
