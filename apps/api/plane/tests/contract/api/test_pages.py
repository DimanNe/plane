# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
The page endpoints of /api/v1/ that plane-sdk calls (plane/api/pages.py), for workspace pages
and for project pages.
"""

import base64
import datetime
import typing as t

import pytest
import requests
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.celery as plane_celery
import plane.db.models as db_models
import plane.tests.contract.page_helpers as page_helpers

pytestmark = [pytest.mark.django_db, pytest.mark.contract]


@pytest.fixture(params=["workspace", "project"])
def project(
    request: pytest.FixtureRequest, workspace: db_models.Workspace, create_user: db_models.User
) -> t.Optional[db_models.Project]:
    """The project of the pages under test, or None for workspace pages. Every test runs for both."""
    return page_helpers.create_project(workspace, create_user) if request.param == "project" else None


@pytest.fixture
def run_tasks_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plane_celery.app.conf, "task_always_eager", True)


class Live:
    """Stands for the live server: records what the API sends it and answers with a document or a failure."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.requests: t.List[t.Dict[str, t.Any]] = []
        self.document: t.Optional[t.Dict[str, t.Any]] = None
        monkeypatch.setattr(requests, "post", self.post)

    def post(
        self, url: str, json: t.Dict[str, t.Any], headers: t.Dict[str, str], **options: t.Any
    ) -> requests.Response:
        self.requests.append({"url": url, "json": json, "headers": headers})
        if self.document is None:
            raise requests.ConnectionError()
        response: requests.Response = requests.Response()
        response.status_code = 200
        response.json = lambda: self.document
        return response


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch, settings: t.Any) -> Live:
    settings.LIVE_URL = "http://live.test/live/"
    settings.LIVE_SERVER_SECRET_KEY = "live-secret"
    return Live(monkeypatch)


def get_pages_url(workspace: db_models.Workspace, project: t.Optional[db_models.Project]) -> str:
    scope: str = f"projects/{project.id}/" if project else ""
    return f"/api/v1/workspaces/{workspace.slug}/{scope}pages/"


def get_page_url(page: db_models.Page, project: t.Optional[db_models.Project], action: str = "") -> str:
    return f"{get_pages_url(page.workspace, project)}{page.id}/{action}"


def test_list_returns_the_pages_of_the_scope_in_one_page_of_results(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, sort_order=1)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=page, sort_order=2)
    other_project: db_models.Project = page_helpers.create_project(workspace, create_user)
    page_helpers.create_page(workspace, create_user, None if project else other_project)
    page_helpers.create_page(workspace, page_helpers.create_member(workspace), project, access=1)

    response: api_response.Response = api_key_client.get(get_pages_url(workspace, project))

    assert (response.status_code, response.json()["results"]) == (
        200,
        [page_helpers.get_page_body(page), page_helpers.get_page_body(nested)],
    )


def test_retrieve_returns_the_page_with_its_description(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, description_html="<p>Text</p>")

    response: api_response.Response = api_key_client.get(get_page_url(page, project))

    assert (response.status_code, response.json()) == (200, page_helpers.get_page_detail_body(page))


def test_page_of_another_scope_is_not_served(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    other_project: db_models.Project = page_helpers.create_project(workspace, create_user)
    wiki_page: db_models.Page = page_helpers.create_page(workspace, create_user)
    project_page: db_models.Page = page_helpers.create_page(workspace, create_user, other_project)

    # the permission of project pages refuses a page that is not in the project
    refusal: int = 403 if project else 404
    assert (
        api_key_client.get(get_page_url(wiki_page if project else project_page, project)).status_code,
        api_key_client.get(get_page_url(project_page, project)).status_code,
    ) == (refusal, refusal)


def test_create_returns_the_new_page(
    workspace: db_models.Workspace,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    response: api_response.Response = api_key_client.post(
        get_pages_url(workspace, project),
        {"name": "Guide", "description_html": "<p>Text</p>", "access": 1, "color": "#fff", "external_id": "7"},
        format="json",
    )

    page: db_models.Page = db_models.Page.objects.get(pk=response.json()["id"])
    assert (
        response.status_code,
        response.json(),
        (page.name, page.description_html, page.access, page.color, page.external_id, page.is_global),
        list(page.project_pages.values_list("project_id", flat=True)),
    ) == (
        201,
        page_helpers.get_page_detail_body(page),
        ("Guide", "<p>Text</p>", 1, "#fff", "7", project is None),
        [project.id] if project else [],
    )


def test_create_with_a_parent_nests_the_page_with_the_access_of_the_parent(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, project, access=1)

    response: api_response.Response = api_key_client.post(
        get_pages_url(workspace, project),
        {"name": "Nested", "description_html": "<p></p>", "access": 0, "parent_id": str(parent.id)},
        format="json",
    )

    assert (response.status_code, response.json()["parent_id"], response.json()["access"]) == (201, str(parent.id), 1)


def test_create_does_not_nest_under_a_page_of_another_scope(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    other_project: db_models.Project = page_helpers.create_project(workspace, create_user)
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, None if project else other_project)

    response: api_response.Response = api_key_client.post(
        get_pages_url(workspace, project),
        {"name": "Nested", "description_html": "<p></p>", "parent_id": str(parent.id)},
        format="json",
    )

    assert (response.status_code, db_models.Page.objects.count()) == (404, 1)


def test_update_changes_the_name_and_the_description_of_a_page_no_editor_has_opened(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
    live: Live,
    run_tasks_inline: None,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, name="Old")

    response: api_response.Response = api_key_client.put(
        get_page_url(page, project), {"name": "New", "description_html": "<p>New</p>"}, format="json"
    )

    page.refresh_from_db()
    assert (
        response.status_code,
        response.json(),
        (page.name, page.description_html, page.description_binary),
        list(db_models.PageVersion.objects.filter(page=page).values_list("description_html", flat=True)),
        live.requests,
    ) == (200, page_helpers.get_page_detail_body(page), ("New", "<p>New</p>", None), ["<p>New</p>"], [])


def test_update_of_a_page_with_an_editor_document_is_made_in_that_document_by_the_live_server(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
    live: Live,
) -> None:
    page: db_models.Page = page_helpers.create_page(
        workspace, create_user, project, name="Old", description_html="<p>Old</p>", description_binary=b"old document"
    )
    live.document = {
        "description_html": "<p>New, as the editor writes it</p>",
        "description_json": {"type": "doc"},
        "description_binary": base64.b64encode(b"new document").decode(),
    }

    response: api_response.Response = api_key_client.put(
        get_page_url(page, project), {"name": "New", "description_html": "<p>New</p>"}, format="json"
    )

    page.refresh_from_db()
    assert (
        response.status_code,
        live.requests,
        (page.name, page.description_html, page.description_json, bytes(page.description_binary)),
    ) == (
        200,
        [
            {
                "url": "http://live.test/live/page-content/",
                "json": {
                    "page_id": str(page.id),
                    "description_binary": base64.b64encode(b"old document").decode(),
                    "name": "New",
                    "description_html": "<p>New</p>",
                },
                "headers": {"live-server-secret-key": "live-secret"},
            }
        ],
        ("New", "<p>New, as the editor writes it</p>", {"type": "doc"}, b"new document"),
    )


def test_update_writes_nothing_when_the_live_server_does_not_take_the_change(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
    live: Live,
) -> None:
    page: db_models.Page = page_helpers.create_page(
        workspace, create_user, project, name="Old", description_html="<p>Old</p>", description_binary=b"old document"
    )

    response: api_response.Response = api_key_client.put(
        get_page_url(page, project), {"name": "New", "description_html": "<p>New</p>"}, format="json"
    )

    page.refresh_from_db()
    assert (response.status_code, page.name, page.description_html, bytes(page.description_binary)) == (
        502,
        "Old",
        "<p>Old</p>",
        b"old document",
    )


def test_web_app_update_of_a_page_with_an_editor_document_does_not_go_to_the_live_server(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    live: Live,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, name="Old", description_binary=b"document")

    response: api_response.Response = session_client.patch(
        f"/api/workspaces/{workspace.slug}/pages/{page.id}/", {"name": "New"}, format="json"
    )

    page.refresh_from_db()
    assert (response.status_code, page.name, live.requests) == (200, "New", [])


@pytest.mark.parametrize("state", [{"is_locked": True}, {"archived_at": datetime.date(2026, 1, 1)}])
def test_update_of_a_locked_or_archived_page_is_refused(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
    state: t.Dict[str, t.Any],
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, name="Old", **state)

    response: api_response.Response = api_key_client.put(get_page_url(page, project), {"name": "New"}, format="json")

    page.refresh_from_db()
    assert (response.status_code, page.name) == (400, "Old")


def test_archive_archives_the_page_and_its_nested_pages(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    page_helpers.create_page(workspace, create_user, project, parent=page)
    other: db_models.Page = page_helpers.create_page(workspace, create_user, project)

    response: api_response.Response = api_key_client.post(get_page_url(page, project, "archive/"))

    assert (
        response.status_code,
        set(db_models.Page.objects.filter(archived_at__isnull=True).values_list("id", flat=True)),
    ) == (200, {other.id})


def test_unarchive_restores_the_page_and_its_nested_pages(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    today: datetime.date = datetime.date.today()
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today)
    page_helpers.create_page(workspace, create_user, project, archived_at=today, parent=page)
    other: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today)

    response: api_response.Response = api_key_client.delete(get_page_url(page, project, "archive/"))

    assert (
        response.status_code,
        set(db_models.Page.objects.filter(archived_at__isnull=False).values_list("id", flat=True)),
    ) == (204, {other.id})


def test_update_that_unlocks_a_locked_page_is_taken(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, name="Old", is_locked=True)

    response: api_response.Response = api_key_client.put(
        get_page_url(page, project), {"is_locked": False, "name": "New"}, format="json"
    )

    page.refresh_from_db()
    assert (response.status_code, page.is_locked, page.name) == (200, False, "New")


def test_delete_is_refused_until_the_page_is_archived(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)

    refused: api_response.Response = api_key_client.delete(get_page_url(page, project))
    api_key_client.post(get_page_url(page, project, "archive/"))
    deleted: api_response.Response = api_key_client.delete(get_page_url(page, project))

    assert (refused.status_code, refused.json(), deleted.status_code, db_models.Page.objects.count()) == (
        400,
        {"error": "The page should be archived before deleting"},
        204,
        0,
    )


def test_delete_of_a_page_with_nested_pages_follows_the_rule_of_its_scope(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: t.Optional[db_models.Project],
    api_key_client: api_test.APIClient,
) -> None:
    today: datetime.date = datetime.date.today()
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today, parent=page)

    response: api_response.Response = api_key_client.delete(get_page_url(page, project))

    # nested pages of a project page stay as top level archived pages, those of a workspace page go with it
    assert (response.status_code, list(db_models.Page.objects.values_list("id", "parent_id", "archived_at"))) == (
        204,
        [(nested.id, None, today)] if project else [],
    )
