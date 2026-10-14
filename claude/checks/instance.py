"""
A running instance as the checks use it: its address, the accounts of one run, and its two APIs.

Nothing about an instance is written down anywhere. Its address is what the runtime published for the run
directory. A run signs in as an administrator of its own, makes a workspace for itself, and in it an account
and a project for every check, so that two checks never share anything that can change.

Data is built and read back through /api/v1/ with the administrator's token. What only the web app's own API
does (members, the display of a list) is done as the account it belongs to, with that account's session.
"""

import dataclasses as dc
import fcntl
import json
import pathlib as pl
import secrets
import string
import subprocess
import sys
import textwrap
import typing as t
import urllib.error
import urllib.request

REPOSITORY: pl.Path = pl.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "scripts"))

import plane_config  # noqa: E402
import plane_runtime  # noqa: E402

JSONObject: t.TypeAlias = t.Dict[str, t.Any]

# Run by the API's own Python, as the runtime makes its first user. The server limits what one address may do in
# a minute while it is not signed in, and a run does more:
# - the form of the sign-in page lets an address in a few times, and a run has more accounts than that; so an
#   account is signed in where the server keeps its sessions, the way Django's test client does it;
# - a page asks first what instance this is, a question the server answers so many times, since it reads the
#   session for it from the cookie of its admin pages, which a user does not have; without the answer the page
#   says that Plane did not start. So the account's session goes under that cookie's name too.
# The account is also past the pages of a first visit.
SIGN_IN: str = textwrap.dedent("""\
    import importlib
    import json
    import sys
    import django
    django.setup()
    import django.conf as conf
    import django.contrib.auth as auth
    import django.http as http
    import plane.db.models as db_models

    email, password = sys.argv[1:3]
    user, _ = db_models.User.objects.get_or_create(email=email, defaults={"username": email})
    user.set_password(password)
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
    print(json.dumps({"user_id": str(user.id), "cookies": cookies}))
""")

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


@dc.dataclass(frozen=True)
class Project:
    id: str
    identifier: str
    name: str
    states: t.Dict[str, str]


def draw_name(length: int) -> str:
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(length))


def send(
    url: str,
    method: str,
    headers: t.Dict[str, str],
    body: t.Optional[bytes],
    opener: urllib.request.OpenerDirector,
) -> t.Any:
    request: urllib.request.Request = urllib.request.Request(
        url, method=method, headers=headers, data=body
    )
    try:
        response: t.Any
        with opener.open(request, timeout=60) as response:
            text: str = response.read().decode()
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"{method} {url} was answered {error.code}: {error.read().decode()[:400]}"
        ) from None
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
        urllib.request.build_opener(urllib.request.ProxyHandler({})),
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
        urllib.request.build_opener(urllib.request.ProxyHandler({})),
    )


def sign_in(run_dir: pl.Path, email: str, password: str) -> Account:
    """Gives the account with this address a session, and makes the account when there is none."""
    printed: str = (
        plane_runtime.run_docker(
            [
                "exec",
                plane_runtime.get_container_name(run_dir, plane_config.Service.API),
                "python",
                "-c",
                SIGN_IN,
                email,
                password,
            ],
            capture=True,
        )
        .stdout.decode()
        .strip()
        .splitlines()[-1]
    )
    signed_in: JSONObject = json.loads(printed)
    return Account(email, password, signed_in["user_id"], signed_in["cookies"])


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


def make_administrator(run_dir: pl.Path) -> t.Tuple[Account, str]:
    password: str = secrets.token_urlsafe(16)
    printed: str = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY / "scripts/plane_runtime.py"),
            "bootstrap-user",
            "--run-dir",
            str(run_dir),
            "--email",
            ADMINISTRATOR_EMAIL,
            # joined, since a drawn password can begin with "-"
            f"--password={password}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    api_key: str = json.loads(printed.strip().splitlines()[-1])["api_key"]
    return sign_in(run_dir, ADMINISTRATOR_EMAIL, password), api_key


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


def open_instance(run_dir: pl.Path) -> Instance:
    """Makes the instance ready for one run: its administrator, and an empty workspace of the run's own."""
    run_dir = plane_runtime.resolve_run_dir(run_dir)
    url: str = find_url(run_dir)
    administrator: Account
    api_key: str
    administrator, api_key = make_administrator(run_dir)
    remove_workspaces_of_earlier_runs(url, administrator)
    workspace: str = WORKSPACE_PREFIX + draw_name(8)
    call_app(
        url,
        administrator,
        "POST",
        "/workspaces/",
        {"name": "Checks", "slug": workspace, "organization_size": "1"},
    )
    return Instance(url, run_dir, api_key, administrator, workspace)


def close_instance(instance: Instance) -> None:
    call_app(
        instance.url,
        instance.administrator,
        "DELETE",
        f"/workspaces/{instance.workspace}/",
    )


def make_account(instance: Instance, role: int = ROLE_ADMIN) -> Account:
    """A new account that is a member of the run's workspace."""
    account: Account = sign_in(
        instance.run_dir,
        f"{draw_name(12)}@plane.invalid",
        secrets.token_urlsafe(16),
    )
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
    **display_filters: t.Any,
) -> None:
    """The account's choices under Display for the project, as the page keeps them on the server."""
    path: str = (
        f"/workspaces/{instance.workspace}/projects/{project.id}/user-properties/"
    )
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
