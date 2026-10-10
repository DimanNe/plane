# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import datetime
import json
import re
import smtplib
import typing as t
import unittest.mock as mock
import urllib.parse as url_parse

import django.core.cache as django_cache
import django.core.mail.backends.smtp as smtp_backend
import django.core.mail.message as mail_message
import django.test as django_test
import django.utils.timezone as django_timezone
import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.bgtasks.project_add_user_email_task as project_add_user_email_task
import plane.db.models as db_models
import plane.license.models as license_models
import plane.settings.redis as redis_settings
import plane.utils.service_users as service_users

pytestmark = [pytest.mark.django_db, pytest.mark.contract]

JsonObject: t.TypeAlias = t.Dict[str, t.Any]

MEMBER: int = 15
GUEST: int = 5
PASSWORD: str = "Str0ng-Pass!42"
REFUSED: JsonObject = {"detail": "You do not have permission to perform this action."}


@pytest.fixture(name="project")
def create_project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(name="Agents", identifier="AG", workspace=workspace)
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=MEMBER)
    return project


@pytest.fixture(name="other_project")
def create_other_project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(name="Other", identifier="OTH", workspace=workspace)
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=20)
    return project


@pytest.fixture(name="sign_in_is_open")
def open_sign_in() -> t.Iterator[None]:
    """Every way to sign in asks for an instance that is set up, and counts the attempts of an address."""
    license_models.Instance.objects.create(
        instance_name="Test",
        instance_id="test",
        current_version="1.0.0",
        last_checked_at=django_timezone.now(),
        is_setup_done=True,
    )
    django_cache.cache.delete_pattern("throttle_authentication_*")
    yield
    django_cache.cache.delete_pattern("throttle_authentication_*")


def post_name(client: api_test.APIClient, project: db_models.Project, name: t.Any) -> api_response.Response:
    return client.post(
        f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/service-users/", {"name": name}, format="json"
    )


def create_service_user(client: api_test.APIClient, project: db_models.Project) -> db_models.User:
    post_name(client, project, "claude")
    return db_models.User.objects.get(bot_type="SERVICE_USER")


def get_service_users() -> t.List[db_models.User]:
    return list(db_models.User.objects.filter(bot_type="SERVICE_USER").order_by("created_at"))


def get_memberships(user: db_models.User) -> JsonObject:
    """Where the user is a member: the slugs of its workspaces and the names of its projects, with the role and
    whether the membership is active."""
    return {
        "workspaces": set(
            db_models.WorkspaceMember.objects.filter(member=user).values_list("workspace__slug", "role", "is_active")
        ),
        "projects": set(
            db_models.ProjectMember.objects.filter(member=user).values_list("project__name", "role", "is_active")
        ),
    }


def format_timestamp(value: datetime.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def test_create_service_user_answers_with_what_the_member_lists_give_of_it(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    response: api_response.Response = post_name(session_client, project, "claude")

    user: db_models.User = db_models.User.objects.get(display_name="claude")
    workspace_member: db_models.WorkspaceMember = db_models.WorkspaceMember.objects.get(member=user)
    project_member: db_models.ProjectMember = db_models.ProjectMember.objects.get(member=user)
    assert (response.status_code, response.json()) == (
        201,
        {
            "workspace_member": {
                "id": str(workspace_member.id),
                "member": {
                    "id": str(user.id),
                    "first_name": "claude",
                    "last_name": "",
                    "avatar": "",
                    "avatar_url": None,
                    "is_bot": False,
                    "bot_type": "SERVICE_USER",
                    "display_name": "claude",
                },
                "role": MEMBER,
                "is_active": True,
                "created_at": format_timestamp(workspace_member.created_at),
            },
            "project_member": {
                "id": str(project_member.id),
                "role": MEMBER,
                "member": str(user.id),
                "project": str(project.id),
                "original_role": MEMBER,
                "created_at": format_timestamp(project_member.created_at),
            },
        },
    )


def test_create_service_user_makes_a_member_of_the_workspace_and_of_the_project(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    post_name(session_client, project, "  claude  ")

    (user,) = get_service_users()
    assert (user.display_name, get_memberships(user)) == (
        "claude",
        {"workspaces": {("test-workspace", MEMBER, True)}, "projects": {("Agents", MEMBER, True)}},
    )


def test_service_user_has_no_password_no_address_and_asks_for_no_notification_email(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    user: db_models.User = create_service_user(session_client, project)

    assert {
        "is_bot": user.is_bot,
        "has_usable_password": user.has_usable_password(),
        "its address is its user name": user.email == user.username,
        "notification e-mails": list(
            db_models.UserNotificationPreference.objects.filter(user=user).values_list(
                "property_change", "state_change", "comment", "mention", "issue_completed"
            )
        ),
    } == {
        "is_bot": False,
        "has_usable_password": False,
        "its address is its user name": True,
        "notification e-mails": [(False, False, False, False, False)],
    }


@pytest.mark.parametrize(
    "name, expected_address",
    [
        pytest.param("claude", "claude.<random>@service-user", id="a-word"),
        pytest.param("Claude, the 2nd <agent>", "claude-the-2nd-agent.<random>@service-user", id="commas-and-brackets"),
        pytest.param("!!!", "service-user.<random>@service-user", id="no-letter-or-digit"),
        pytest.param("n" * 255, "n" * 64 + ".<random>@service-user", id="longest-name"),
    ],
)
def test_service_user_of_any_name_has_an_address_that_the_email_backend_sends_nothing_to(
    project: db_models.Project, session_client: api_test.APIClient, name: str, expected_address: str
) -> None:
    post_name(session_client, project, name)

    (user,) = get_service_users()
    assert (re.sub("[0-9a-f]{32}", "<random>", user.email), service_users.is_service_user_address(user.email)) == (
        expected_address,
        True,
    )


@pytest.mark.parametrize(
    "name, expected_status, expected_count",
    [
        pytest.param("claude", 200, 1, id="its-name"),
        pytest.param("Claude", 200, 1, id="its-name-in-other-letter-case"),
        pytest.param("claude 2", 201, 2, id="another-name"),
    ],
)
def test_create_service_user_in_another_project_adds_the_one_the_workspace_has_by_that_name(
    project: db_models.Project,
    other_project: db_models.Project,
    session_client: api_test.APIClient,
    name: str,
    expected_status: int,
    expected_count: int,
) -> None:
    post_name(session_client, project, "claude")

    response: api_response.Response = post_name(session_client, other_project, name)

    users: t.List[db_models.User] = get_service_users()
    assert (
        response.status_code,
        len(users),
        response.json()["workspace_member"]["member"]["id"],
        get_memberships(users[-1])["projects"],
    ) == (
        expected_status,
        expected_count,
        str(users[-1].id),
        {("Other", MEMBER, True)} | ({("Agents", MEMBER, True)} if expected_count == 1 else set()),
    )


@pytest.mark.parametrize(
    "membership",
    [
        pytest.param(db_models.ProjectMember, id="removed-from-the-project"),
        pytest.param(db_models.WorkspaceMember, id="removed-from-the-workspace"),
    ],
)
def test_create_service_user_that_was_removed_makes_it_a_member_again(
    project: db_models.Project,
    session_client: api_test.APIClient,
    membership: t.Type[t.Union[db_models.ProjectMember, db_models.WorkspaceMember]],
) -> None:
    user: db_models.User = create_service_user(session_client, project)
    membership.objects.filter(member=user).update(is_active=False)

    response: api_response.Response = post_name(session_client, project, "claude")

    assert (response.status_code, get_service_users(), get_memberships(user)) == (
        200,
        [user],
        {"workspaces": {("test-workspace", MEMBER, True)}, "projects": {("Agents", MEMBER, True)}},
    )


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("person", id="a-person-of-the-workspace"),
        pytest.param("service user of another workspace", id="a-service-user-of-another-workspace"),
    ],
)
def test_create_service_user_with_the_name_of_somebody_else_makes_a_new_user(
    project: db_models.Project, workspace: db_models.Workspace, session_client: api_test.APIClient, kind: str
) -> None:
    other_workspace: db_models.Workspace = db_models.Workspace.objects.create(
        name="Elsewhere", owner=workspace.owner, slug="elsewhere"
    )
    somebody: db_models.User = db_models.User.objects.create(
        username="somebody",
        email="somebody@example.internal",
        display_name="claude",
        bot_type=None if kind == "person" else "SERVICE_USER",
    )
    db_models.WorkspaceMember.objects.create(
        workspace=workspace if kind == "person" else other_workspace, member=somebody, role=MEMBER
    )

    response: api_response.Response = post_name(session_client, project, "claude")

    created: db_models.User = db_models.User.objects.exclude(pk=somebody.pk).get(display_name="claude")
    assert (response.status_code, response.json()["project_member"]["member"], get_memberships(created)) == (
        201,
        str(created.id),
        {"workspaces": {("test-workspace", MEMBER, True)}, "projects": {("Agents", MEMBER, True)}},
    )


@pytest.mark.parametrize(
    "role, name, expected",
    [
        pytest.param(GUEST, "claude", (403, REFUSED), id="guest"),
        pytest.param(None, "claude", (403, REFUSED), id="not-a-member-of-the-project"),
        pytest.param(MEMBER, "   ", (400, {"name": ["This field may not be blank."]}), id="blank-name"),
        pytest.param(MEMBER, None, (400, {"name": ["This field may not be null."]}), id="no-name"),
        pytest.param(
            MEMBER, "c" * 256, (400, {"name": ["Ensure this field has no more than 255 characters."]}), id="long-name"
        ),
    ],
)
def test_create_service_user_that_is_refused_creates_nobody(
    project: db_models.Project,
    session_client: api_test.APIClient,
    role: t.Optional[int],
    name: t.Optional[str],
    expected: t.Tuple[int, JsonObject],
) -> None:
    members: db_models.QuerySet = db_models.ProjectMember.objects.filter(project=project)
    members.update(role=role) if role else members.delete()

    response: api_response.Response = post_name(session_client, project, name)

    assert ((response.status_code, response.json()), get_service_users()) == (expected, [])


def test_service_user_is_in_the_member_lists_of_the_web_app(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    user: db_models.User = create_service_user(session_client, project)
    urls: t.List[str] = [
        f"/api/workspaces/{project.workspace.slug}/members/",
        f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/members/",
    ]

    workspace_members: t.List[JsonObject]
    project_members: t.List[JsonObject]
    workspace_members, project_members = [session_client.get(url).json() for url in urls]

    assert (
        [member["member"]["bot_type"] for member in workspace_members if member["member"]["id"] == str(user.id)],
        [member["role"] for member in project_members if member["member"] == str(user.id)],
    ) == (["SERVICE_USER"], [MEMBER])


def test_service_user_is_a_member_and_an_assignee_through_api_v1(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    user: db_models.User = service_users.add_service_user_to_project(project, "claude")[1].member
    url: str = f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}"

    members: t.List[JsonObject] = api_key_client.get(f"{url}/members/").json()
    created: api_response.Response = api_key_client.post(
        f"{url}/work-items/", {"name": "Task", "assignees": [str(user.id)]}, format="json"
    )
    assigned: t.List[str] = api_key_client.get(f"{url}/work-items/{created.json()['id']}/").json()["assignees"]
    cleared: api_response.Response = api_key_client.patch(
        f"{url}/work-items/{created.json()['id']}/", {"assignees": []}, format="json"
    )

    assert (
        [member["display_name"] for member in members if member["id"] == str(user.id)],
        (created.status_code, assigned),
        (cleared.status_code, list(db_models.IssueAssignee.objects.values_list("assignee_id", flat=True))),
    ) == (["claude"], (201, [str(user.id)]), (200, []))


@pytest.mark.parametrize(
    "path, address_given_by_hand, expected_error",
    [
        pytest.param("/auth/sign-in/", None, "INVALID_EMAIL_SIGN_IN", id="password"),
        pytest.param("/auth/magic-sign-in/", None, "INVALID_EMAIL", id="magic-code"),
        pytest.param(
            "/auth/sign-in/", "claude@example.internal", "BOT_USER_LOGIN_FORBIDDEN", id="password-of-an-address-by-hand"
        ),
        pytest.param(
            "/auth/magic-sign-in/",
            "claude@example.internal",
            "BOT_USER_LOGIN_FORBIDDEN",
            id="magic-code-of-an-address-by-hand",
        ),
    ],
)
def test_service_user_cannot_sign_in(
    project: db_models.Project,
    session_client: api_test.APIClient,
    sign_in_is_open: None,
    path: str,
    address_given_by_hand: t.Optional[str],
    expected_error: str,
) -> None:
    """Also when somebody stored a magic code for it, or gave it an address and a password in the database."""
    user: db_models.User = create_service_user(session_client, project)
    if address_given_by_hand:
        user.email = address_given_by_hand
        user.set_password(PASSWORD)
        user.save()
    code: JsonObject = {"current_attempt": 0, "email": user.email, "token": "123456"}
    redis_settings.redis_instance().set(f"magic_{user.email}", json.dumps(code), ex=60)
    visitor: django_test.Client = django_test.Client()

    response: t.Any = visitor.post(path, {"email": user.email, "password": PASSWORD, "code": "123456"})

    query: t.Dict[str, t.List[str]] = url_parse.parse_qs(url_parse.urlsplit(response["Location"]).query)
    assert (response.status_code, query["error_message"], "_auth_user_id" in visitor.session) == (
        302,
        [expected_error],
        False,
    )


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/auth/magic-generate/", id="magic-code"),
        pytest.param("/auth/forgot-password/", id="forgot-password"),
    ],
)
def test_no_sign_in_email_is_written_for_a_service_user(
    project: db_models.Project, session_client: api_test.APIClient, sign_in_is_open: None, path: str
) -> None:
    user: db_models.User = create_service_user(session_client, project)
    visitor: api_test.APIClient = api_test.APIClient()
    visitor.raise_request_exception = False

    with (
        mock.patch("plane.authentication.views.app.magic.magic_link.delay") as magic_link,
        mock.patch("plane.authentication.views.app.password_management.forgot_password.delay") as forgot_password,
    ):
        response: api_response.Response = visitor.post(path, {"email": user.email}, format="json")

    assert (response.status_code >= 400, magic_link.call_count, forgot_password.call_count) == (True, 0, 0)


def get_message(*recipients: str) -> mail_message.EmailMessage:
    return mail_message.EmailMessage(subject="Subject", body="Body", from_email="plane@example.internal", to=recipients)


@pytest.mark.parametrize(
    "messages, expected_recipients",
    [
        pytest.param([("0123@service-user",)], [], id="to-a-service-user-alone"),
        pytest.param(
            [("person@example.internal", "0123@service-user")], [["person@example.internal"]], id="to-a-person-too"
        ),
        pytest.param(
            [("0123@service-user",), ("person@example.internal",), ("Claude <ABCD@Service-User>",)],
            [["person@example.internal"]],
            id="one-message-of-several",
        ),
        pytest.param(
            [("bob@service-user.example",)], [["bob@service-user.example"]], id="an-address-that-only-looks-alike"
        ),
    ],
)
def test_email_backend_sends_nothing_to_a_service_user(
    messages: t.List[t.Tuple[str, ...]], expected_recipients: t.List[t.List[str]]
) -> None:
    backend: service_users.EmailBackend = service_users.EmailBackend(host="smtp.example.internal")
    sent: t.List[t.List[str]] = []

    def record(self: smtp_backend.EmailBackend, email_messages: t.List[mail_message.EmailMessage]) -> int:
        sent.extend(message.recipients() for message in email_messages)
        return len(email_messages)

    with mock.patch.object(smtp_backend.EmailBackend, "send_messages", record):
        backend.send_messages([get_message(*recipients) for recipients in messages])

    assert sent == expected_recipients


def test_adding_a_service_user_to_a_project_in_the_member_settings_opens_no_connection_to_send_email(
    project: db_models.Project,
    other_project: db_models.Project,
    session_client: api_test.APIClient,
    settings: t.Any,
) -> None:
    settings.EMAIL_BACKEND = "plane.utils.service_users.EmailBackend"
    user: db_models.User = create_service_user(session_client, project)
    task: t.Any = project_add_user_email_task.project_add_user_email

    with (
        mock.patch.object(task, "delay", side_effect=task.run) as written,
        mock.patch.object(smtplib, "SMTP") as smtp,
    ):
        response: api_response.Response = session_client.post(
            f"/api/workspaces/{project.workspace.slug}/projects/{other_project.id}/members/",
            {"members": [{"member_id": str(user.id), "role": MEMBER}]},
            format="json",
        )

    assert (response.status_code, written.call_count, smtp.call_count, get_memberships(user)["projects"]) == (
        201,
        1,
        0,
        {("Agents", MEMBER, True), ("Other", MEMBER, True)},
    )
