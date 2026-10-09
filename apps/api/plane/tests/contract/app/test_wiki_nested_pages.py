# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Workspace pages (the wiki) and nested pages as the web app uses them, by the rules of
https://docs.plane.so/pages/wiki and https://docs.plane.so/pages/nested-pages.
"""

import datetime
import typing as t
import uuid

import django.db.models.signals as django_signals
import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.bgtasks.page_transaction_task as page_transaction_task
import plane.celery as plane_celery
import plane.db.models as db_models
import plane.tests.contract.page_helpers as page_helpers

pytestmark = [pytest.mark.django_db, pytest.mark.contract]

PUBLIC: int = db_models.Page.PUBLIC_ACCESS
PRIVATE: int = db_models.Page.PRIVATE_ACCESS


@pytest.fixture
def project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    return page_helpers.create_project(workspace, create_user)


@pytest.fixture
def run_tasks_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plane_celery.app.conf, "task_always_eager", True)


def get_pages_url(workspace: db_models.Workspace, project: t.Optional[db_models.Project] = None) -> str:
    scope: str = f"projects/{project.id}/" if project else ""
    return f"/api/workspaces/{workspace.slug}/{scope}pages/"


def get_page_url(page: db_models.Page, project: t.Optional[db_models.Project] = None, action: str = "") -> str:
    return f"{get_pages_url(page.workspace, project)}{page.id}/{action}"


def get_placements(*pages: db_models.Page) -> t.List[t.Tuple[t.Optional[uuid.UUID], int, t.Optional[uuid.UUID]]]:
    """The parent, the access and the collection of each page, as stored."""
    placements: t.List[t.Tuple[t.Optional[uuid.UUID], int, t.Optional[uuid.UUID]]] = []
    page: db_models.Page
    for page in pages:
        page.refresh_from_db()
        placements.append((page.parent_id, page.access, page.collection_id))
    return placements


def get_default_collection(workspace: db_models.Workspace) -> db_models.Collection:
    return db_models.Collection.objects.get(workspace=workspace, is_default=True)


def create_collection(workspace: db_models.Workspace, owner: db_models.User, access: int) -> db_models.Collection:
    return db_models.Collection.objects.create(workspace=workspace, owned_by=owner, name="Handbook", access=access)


def get_collections_url(workspace: db_models.Workspace) -> str:
    return f"/api/workspaces/{workspace.slug}/collections/"


def get_project_page_body(page: db_models.Page, project: db_models.Project) -> t.Dict[str, t.Any]:
    return {
        "id": str(page.id),
        "name": page.name,
        "owned_by": str(page.owned_by_id),
        "access": page.access,
        "color": page.color,
        "parent": page_helpers.get_id(page.parent_id),
        "parent_id": page_helpers.get_id(page.parent_id),
        "is_favorite": False,
        "is_locked": page.is_locked,
        "archived_at": None,
        "workspace": str(page.workspace_id),
        "created_at": page_helpers.get_time(page.created_at),
        "updated_at": page_helpers.get_time(page.updated_at),
        "created_by": page_helpers.get_id(page.created_by_id),
        "updated_by": page_helpers.get_id(page.updated_by_id),
        "view_props": page.view_props,
        "logo_props": page.logo_props,
        "label_ids": [],
        "project_ids": [str(project.id)],
    }


def test_wiki_turned_off_refuses_wiki_pages_and_leaves_project_pages(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    page_helpers.create_page(workspace, create_user)

    setting: api_response.Response = session_client.patch(
        f"/api/workspaces/{workspace.slug}/", {"is_wiki_enabled": False}, format="json"
    )

    assert (
        setting.status_code,
        session_client.get(get_pages_url(workspace)).status_code,
        session_client.get(f"/api/workspaces/{workspace.slug}/collections/").status_code,
        session_client.get(get_pages_url(workspace, project)).status_code,
    ) == (200, 403, 403, 200)


def test_guest_is_refused_the_wiki(workspace: db_models.Workspace) -> None:
    guest: db_models.User = page_helpers.create_member(workspace, role=5)

    response: api_response.Response = page_helpers.get_client(guest).get(get_pages_url(workspace))

    assert response.status_code == 403


def test_private_page_is_served_to_its_owner_only(workspace: db_models.Workspace, create_user: db_models.User) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PRIVATE)
    other_member: api_test.APIClient = page_helpers.get_client(page_helpers.create_member(workspace))
    owner: api_test.APIClient = page_helpers.get_client(create_user)

    assert (
        other_member.get(get_pages_url(workspace)).json()["results"],
        other_member.get(get_page_url(page)).status_code,
        owner.get(get_pages_url(workspace)).json()["results"],
        owner.get(get_page_url(page)).json(),
    ) == ([], 404, [page_helpers.get_page_body(page)], page_helpers.get_page_detail_body(page))


def test_public_pages_created_without_a_collection_share_the_default_collection(
    workspace: db_models.Workspace, session_client: api_test.APIClient
) -> None:
    first: api_response.Response = session_client.post(get_pages_url(workspace), {"name": "First"}, format="json")
    second: api_response.Response = session_client.post(get_pages_url(workspace), {"name": "Second"}, format="json")

    default: db_models.Collection = get_default_collection(workspace)
    assert (
        first.status_code,
        first.json()["collection_id"],
        second.json()["collection_id"],
        default.name,
        default.access,
    ) == (201, str(default.id), str(default.id), "General", PUBLIC)


def test_private_page_created_without_a_collection_stays_outside_collections(
    workspace: db_models.Workspace, session_client: api_test.APIClient
) -> None:
    response: api_response.Response = session_client.post(
        get_pages_url(workspace), {"name": "Notes", "access": PRIVATE}, format="json"
    )

    page: db_models.Page = db_models.Page.objects.get(pk=response.json()["id"])
    assert (response.json(), page.collection_id, db_models.Collection.objects.count()) == (
        page_helpers.get_page_detail_body(page),
        None,
        0,
    )


@pytest.mark.parametrize("collection_access", [PUBLIC, PRIVATE])
def test_page_created_in_a_collection_takes_the_access_of_the_collection(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    collection_access: int,
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, collection_access)

    response: api_response.Response = session_client.post(
        get_pages_url(workspace),
        {"name": "Page", "access": PRIVATE - collection_access, "collection_id": str(collection.id)},
        format="json",
    )

    page: db_models.Page = db_models.Page.objects.get(pk=response.json()["id"])
    assert get_placements(page) == [(None, collection_access, collection.id)]


@pytest.mark.parametrize("parent_access", [PUBLIC, PRIVATE])
def test_nested_page_is_created_with_the_access_and_collection_of_its_parent(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    parent_access: int,
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, parent_access)
    parent: db_models.Page = page_helpers.create_page(
        workspace, create_user, access=parent_access, collection=collection
    )

    response: api_response.Response = session_client.post(
        get_pages_url(workspace),
        {"name": "Nested", "access": PRIVATE - parent_access, "parent_id": str(parent.id)},
        format="json",
    )

    page: db_models.Page = db_models.Page.objects.get(pk=response.json()["id"])
    assert (response.status_code, get_placements(page)) == (201, [(parent.id, parent_access, collection.id)])


def test_page_is_not_created_under_an_archived_page(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, archived_at=datetime.date.today())

    response: api_response.Response = session_client.post(
        get_pages_url(workspace), {"name": "Nested", "parent_id": str(parent.id)}, format="json"
    )

    assert (response.status_code, db_models.Page.objects.count()) == (400, 1)


def test_page_is_not_created_with_a_parent_and_a_collection_other_than_the_parent_has(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PUBLIC)
    parent: db_models.Page = page_helpers.create_page(workspace, create_user)

    response: api_response.Response = session_client.post(
        get_pages_url(workspace),
        {"name": "Nested", "parent_id": str(parent.id), "collection_id": str(collection.id)},
        format="json",
    )

    assert (response.status_code, db_models.Page.objects.count()) == (400, 1)


def test_new_page_is_ordered_after_the_existing_pages(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    existing: db_models.Page = page_helpers.create_page(workspace, create_user, sort_order=200000)

    response: api_response.Response = session_client.post(get_pages_url(workspace), {"name": "Last"}, format="json")

    listed: api_response.Response = session_client.get(get_pages_url(workspace))
    assert [page["id"] for page in listed.json()["results"]] == [str(existing.id), response.json()["id"]]


def test_copy_of_a_wiki_page_is_ordered_after_the_existing_pages(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, sort_order=100)
    last: db_models.Page = page_helpers.create_page(workspace, create_user, sort_order=200)

    response: api_response.Response = session_client.post(get_page_url(page, action="duplicate/"))

    listed: api_response.Response = session_client.get(get_pages_url(workspace))
    assert [listed_page["id"] for listed_page in listed.json()["results"]] == [
        str(page.id),
        str(last.id),
        response.json()["id"],
    ]


def test_new_collection_is_ordered_after_the_existing_collections(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    existing: db_models.Collection = create_collection(workspace, create_user, PUBLIC)

    response: api_response.Response = session_client.post(
        get_collections_url(workspace), {"name": "Runbooks"}, format="json"
    )

    collection: db_models.Collection = db_models.Collection.objects.get(pk=response.json()["id"])
    assert (response.status_code, response.json(), collection.sort_order) == (
        201,
        page_helpers.get_collection_body(collection),
        existing.sort_order + db_models.Page.DEFAULT_SORT_ORDER,
    )


def test_default_collection_created_after_another_collection_is_ordered_first(
    workspace: db_models.Workspace, session_client: api_test.APIClient
) -> None:
    created: api_response.Response = session_client.post(
        get_collections_url(workspace), {"name": "Runbooks"}, format="json"
    )
    session_client.post(get_pages_url(workspace), {"name": "First public page"}, format="json")

    listed: api_response.Response = session_client.get(get_collections_url(workspace))

    assert [collection["id"] for collection in listed.json()] == [
        str(get_default_collection(workspace).id),
        created.json()["id"],
    ]


@pytest.mark.parametrize("new_parent", ["itself", "nested", "nested twice"])
@pytest.mark.parametrize("in_project", [False, True])
def test_page_is_not_nested_under_itself_or_a_page_nested_under_it(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    new_parent: str,
    in_project: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=page)
    nested_twice: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=nested)
    parents: t.Dict[str, db_models.Page] = {"itself": page, "nested": nested, "nested twice": nested_twice}

    response: api_response.Response = session_client.patch(
        get_page_url(page, project),
        {"parent_id": str(parents[new_parent].id)},
        format="json",
    )

    page.refresh_from_db()
    assert (response.status_code, page.parent_id) == (400, None)


def test_nesting_gives_the_page_and_its_nested_pages_the_access_and_collection_of_the_parent(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PUBLIC)
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC, collection=collection)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PRIVATE)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, access=PRIVATE, parent=page)

    response: api_response.Response = session_client.patch(
        get_page_url(page), {"parent_id": str(parent.id)}, format="json"
    )

    assert (response.status_code, get_placements(page, nested)) == (
        200,
        [(parent.id, PUBLIC, collection.id), (page.id, PUBLIC, collection.id)],
    )


def test_moving_a_nested_page_to_the_top_level_keeps_its_collection(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PUBLIC)
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, collection=collection)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, collection=collection, parent=parent)

    response: api_response.Response = session_client.patch(get_page_url(page), {"parent_id": None}, format="json")

    assert (response.status_code, get_placements(page)) == (200, [(None, PUBLIC, collection.id)])


def test_reordering_a_nested_page_keeps_it_nested(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    parent: db_models.Page = page_helpers.create_page(workspace, create_user)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, parent=parent)

    response: api_response.Response = session_client.patch(get_page_url(page), {"sort_order": 10}, format="json")

    page.refresh_from_db()
    assert (response.status_code, page.parent_id, page.sort_order) == (200, parent.id, 10)


def test_moving_a_page_to_a_collection_changes_the_access_of_its_nested_pages(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PRIVATE)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC, parent=page)

    response: api_response.Response = session_client.patch(
        get_page_url(page), {"collection_id": str(collection.id)}, format="json"
    )

    assert (response.status_code, get_placements(page, nested)) == (
        200,
        [(None, PRIVATE, collection.id), (page.id, PRIVATE, collection.id)],
    )


@pytest.mark.parametrize("change", ["access", "collection_id"])
def test_nested_page_does_not_change_access_or_collection_on_its_own(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    change: str,
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PRIVATE)
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC, parent=parent)
    changes: t.Dict[str, t.Union[int, str]] = {"access": PRIVATE, "collection_id": str(collection.id)}

    response: api_response.Response = session_client.patch(get_page_url(page), {change: changes[change]}, format="json")

    assert (response.status_code, get_placements(page)) == (400, [(parent.id, PUBLIC, None)])


def test_making_a_page_private_takes_it_and_its_nested_pages_out_of_the_public_collection(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PUBLIC)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC, collection=collection)
    nested: db_models.Page = page_helpers.create_page(
        workspace, create_user, access=PUBLIC, collection=collection, parent=page
    )

    response: api_response.Response = session_client.patch(get_page_url(page), {"access": PRIVATE}, format="json")

    assert (response.status_code, get_placements(page, nested)) == (
        200,
        [(None, PRIVATE, None), (page.id, PRIVATE, None)],
    )


def test_making_a_page_public_files_it_and_its_nested_pages_in_the_default_collection(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PRIVATE)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, access=PRIVATE, parent=page)

    response: api_response.Response = session_client.patch(get_page_url(page), {"access": PUBLIC}, format="json")

    default: db_models.Collection = get_default_collection(workspace)
    assert (response.status_code, get_placements(page, nested)) == (
        200,
        [(None, PUBLIC, default.id), (page.id, PUBLIC, default.id)],
    )


def test_access_of_a_page_is_changed_by_its_owner_only(
    workspace: db_models.Workspace, create_user: db_models.User
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC)
    other_member: api_test.APIClient = page_helpers.get_client(page_helpers.create_member(workspace))

    response: api_response.Response = other_member.patch(get_page_url(page), {"access": PRIVATE}, format="json")

    assert (response.status_code, get_placements(page)) == (400, [(None, PUBLIC, None)])


@pytest.mark.parametrize("destination", ["parent_id", "collection_id"])
def test_page_is_moved_to_a_place_of_another_access_by_its_owner_only(
    workspace: db_models.Workspace, create_user: db_models.User, destination: str
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC)
    other_member: db_models.User = page_helpers.create_member(workspace)
    destinations: t.Dict[str, uuid.UUID] = {
        "parent_id": page_helpers.create_page(workspace, other_member, access=PRIVATE).id,
        "collection_id": create_collection(workspace, other_member, PRIVATE).id,
    }

    response: api_response.Response = page_helpers.get_client(other_member).patch(
        get_page_url(page), {destination: str(destinations[destination])}, format="json"
    )

    assert (response.status_code, get_placements(page)) == (400, [(None, PUBLIC, None)])


def test_adding_pages_to_a_collection_skips_the_pages_of_other_owners_that_would_change_access(
    workspace: db_models.Workspace, create_user: db_models.User
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC)
    other_member: db_models.User = page_helpers.create_member(workspace)
    collection: db_models.Collection = create_collection(workspace, other_member, PRIVATE)

    response: api_response.Response = page_helpers.get_client(other_member).post(
        f"{get_collections_url(workspace)}{collection.id}/pages/", {"page_ids": [str(page.id)]}, format="json"
    )

    assert (response.status_code, response.json(), get_placements(page)) == (201, [], [(None, PUBLIC, None)])


def test_page_of_a_collection_is_moved_to_a_collection_of_another_access_by_its_owner_only(
    workspace: db_models.Workspace, create_user: db_models.User
) -> None:
    public: db_models.Collection = create_collection(workspace, create_user, PUBLIC)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC, collection=public)
    other_member: db_models.User = page_helpers.create_member(workspace)
    private: db_models.Collection = create_collection(workspace, other_member, PRIVATE)

    response: api_response.Response = page_helpers.get_client(other_member).patch(
        f"{get_collections_url(workspace)}{public.id}/pages/{page.id}/", {"collection": str(private.id)}, format="json"
    )

    assert (response.status_code, get_placements(page)) == (400, [(None, PUBLIC, public.id)])


@pytest.mark.parametrize("in_project", [False, True])
def test_archiving_a_page_archives_its_nested_pages(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    in_project: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    page_helpers.create_page(workspace, create_user, project, parent=page)
    other: db_models.Page = page_helpers.create_page(workspace, create_user, project)

    response: api_response.Response = session_client.post(get_page_url(page, project, "archive/"))

    assert (
        response.status_code,
        set(db_models.Page.objects.filter(archived_at__isnull=True).values_list("id", flat=True)),
    ) == (200, {other.id})


@pytest.mark.parametrize("in_project", [False, True])
def test_restoring_a_page_restores_its_nested_pages(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    in_project: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    today: datetime.date = datetime.date.today()
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today)
    page_helpers.create_page(workspace, create_user, project, archived_at=today, parent=page)
    other: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today)

    response: api_response.Response = session_client.delete(get_page_url(page, project, "archive/"))

    assert (
        response.status_code,
        set(db_models.Page.objects.filter(archived_at__isnull=False).values_list("id", flat=True)),
    ) == (204, {other.id})


@pytest.mark.parametrize("in_project", [False, True])
def test_archiving_a_page_removes_it_and_its_nested_pages_from_favorites(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    in_project: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=page)
    other: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    favorite: db_models.Page
    for favorite in [page, nested, other]:
        db_models.UserFavorite.objects.create(
            workspace=workspace, project=project, user=create_user, entity_type="page", entity_identifier=favorite.id
        )

    session_client.post(get_page_url(page, project, "archive/"))

    assert list(db_models.UserFavorite.objects.values_list("entity_identifier", flat=True)) == [other.id]


@pytest.mark.parametrize("in_project", [False, True])
def test_nested_page_is_not_restored_while_its_parent_is_archived(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    in_project: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    today: datetime.date = datetime.date.today()
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today, parent=parent)

    response: api_response.Response = session_client.delete(get_page_url(page, project, "archive/"))

    page.refresh_from_db()
    assert (response.status_code, page.archived_at, page.parent_id) == (400, today, parent.id)


def test_deleting_an_archived_wiki_page_deletes_its_nested_pages(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    today: datetime.date = datetime.date.today()
    page: db_models.Page = page_helpers.create_page(workspace, create_user, archived_at=today)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, archived_at=today, parent=page)
    page_helpers.create_page(workspace, create_user, archived_at=today, parent=nested)
    other: db_models.Page = page_helpers.create_page(workspace, create_user, archived_at=today)

    response: api_response.Response = session_client.delete(get_page_url(page))

    assert (response.status_code, list(db_models.Page.objects.values_list("id", flat=True))) == (204, [other.id])


def test_deleting_an_archived_project_page_keeps_its_nested_pages_as_top_level_archived_pages(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    today: datetime.date = datetime.date.today()
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, archived_at=today, parent=page)

    response: api_response.Response = session_client.delete(get_page_url(page, project))

    assert (
        response.status_code,
        list(db_models.Page.objects.values_list("id", "parent_id", "archived_at")),
    ) == (204, [(nested.id, None, today)])


def test_wiki_page_is_not_deleted_before_it_is_archived(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user)

    response: api_response.Response = session_client.delete(get_page_url(page))

    assert (response.status_code, response.json(), db_models.Page.objects.filter(pk=page.id).exists()) == (
        400,
        {"error": "The page should be archived before deleting"},
        True,
    )


@pytest.mark.parametrize(
    "method, action, archived, refusal",
    [("post", "archive/", False, 400), ("delete", "archive/", True, 400), ("delete", "", True, 403)],
)
def test_wiki_page_is_archived_restored_and_deleted_by_its_owner_or_an_admin_only(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    method: str,
    action: str,
    archived: bool,
    refusal: int,
) -> None:
    today: datetime.date = datetime.date.today()
    page: db_models.Page = page_helpers.create_page(workspace, create_user, archived_at=today if archived else None)
    other_member: api_test.APIClient = page_helpers.get_client(page_helpers.create_member(workspace))

    response: api_response.Response = getattr(other_member, method)(get_page_url(page, action=action))

    page.refresh_from_db()
    assert (response.status_code, page.archived_at) == (refusal, today if archived else None)


@pytest.mark.parametrize("in_project", [False, True])
@pytest.mark.parametrize("recursive", [False, True])
def test_lock_and_unlock_include_the_nested_pages_when_asked(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    in_project: bool,
    recursive: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=page)
    pages: t.List[db_models.Page] = [page, nested]

    locked: api_response.Response = session_client.post(
        get_page_url(page, project, "lock/"), {"recursive": recursive}, format="json"
    )
    locked_ids: t.Set[uuid.UUID] = set(db_models.Page.objects.filter(is_locked=True).values_list("id", flat=True))
    db_models.Page.objects.update(is_locked=True)
    unlocked: api_response.Response = session_client.delete(
        get_page_url(page, project, "lock/"), {"recursive": recursive}, format="json"
    )

    changed_ids: t.Set[uuid.UUID] = {changed.id for changed in (pages if recursive else [page])}
    assert (
        locked.status_code,
        locked_ids,
        unlocked.status_code,
        set(db_models.Page.objects.filter(is_locked=False).values_list("id", flat=True)),
    ) == (204, changed_ids, 204, changed_ids)


@pytest.mark.parametrize("state", [{"is_locked": True}, {"archived_at": datetime.date(2026, 1, 1)}])
def test_locked_or_archived_wiki_page_refuses_an_update(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    state: t.Dict[str, t.Any],
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, name="Name", **state)

    response: api_response.Response = session_client.patch(get_page_url(page), {"name": "Changed"}, format="json")

    page.refresh_from_db()
    assert (response.status_code, page.name) == (400, "Name")


def test_wiki_page_description_is_read_and_written_as_the_editor_document(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user)
    document: t.Dict[str, t.Any] = {
        "description_binary": "AAECAw==",
        "description_html": "<p>Updated</p>",
        "description_json": {"type": "doc", "content": [{"type": "paragraph"}]},
    }

    empty: api_response.Response = session_client.get(get_page_url(page, action="description/"))
    written: api_response.Response = session_client.patch(
        get_page_url(page, action="description/"), document, format="json"
    )
    read: api_response.Response = session_client.get(get_page_url(page, action="description/"))

    page.refresh_from_db()
    assert (
        empty.content,
        written.status_code,
        written.json(),
        read.content,
        page.description_html,
        page.description_json,
    ) == (
        b"",
        200,
        {"message": "Updated successfully"},
        b"\x00\x01\x02\x03",
        document["description_html"],
        document["description_json"],
    )


@pytest.mark.parametrize(
    "state, error",
    [
        ({"is_locked": True}, {"error_code": 4701, "error_message": "PAGE_LOCKED"}),
        ({"archived_at": datetime.date(2026, 1, 1)}, {"error_code": 4702, "error_message": "PAGE_ARCHIVED"}),
    ],
)
def test_locked_or_archived_wiki_page_refuses_a_description_write(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    state: t.Dict[str, t.Any],
    error: t.Dict[str, t.Any],
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, description_html="<p>Kept</p>", **state)

    response: api_response.Response = session_client.patch(
        get_page_url(page, action="description/"), {"description_html": "<p>Changed</p>"}, format="json"
    )

    page.refresh_from_db()
    assert (response.status_code, response.json(), page.description_html) == (400, error, "<p>Kept</p>")


@pytest.mark.parametrize("in_project", [False, True])
def test_description_writes_of_one_editing_session_keep_one_version_with_the_latest_content(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    run_tasks_inline: None,
    in_project: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)

    html: str
    for html in ["<p>First</p>", "<p>Second</p>"]:
        session_client.patch(get_page_url(page, project, "description/"), {"description_html": html}, format="json")

    assert list(db_models.PageVersion.objects.filter(page=page).values_list("description_html", "owned_by_id")) == [
        ("<p>Second</p>", create_user.id)
    ]


def test_wiki_page_versions_are_listed_and_retrieved(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user)
    version: db_models.PageVersion = db_models.PageVersion.objects.create(
        workspace=workspace, page=page, owned_by=create_user, description_html="<p>Earlier</p>"
    )
    other_page: db_models.Page = page_helpers.create_page(workspace, create_user)
    db_models.PageVersion.objects.create(workspace=workspace, page=other_page, owned_by=create_user)

    listed: api_response.Response = session_client.get(get_page_url(page, action="versions/"))
    retrieved: api_response.Response = session_client.get(get_page_url(page, action=f"versions/{version.id}/"))

    assert (
        [listed_version["id"] for listed_version in listed.json()],
        retrieved.json()["description_html"],
        session_client.get(get_page_url(other_page, action=f"versions/{version.id}/")).status_code,
    ) == ([str(version.id)], "<p>Earlier</p>", 404)


def test_project_page_is_added_to_and_removed_from_favorites(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    favorite_url: str = f"/api/workspaces/{workspace.slug}/projects/{project.id}/favorite-pages/{page.id}/"

    added: api_response.Response = session_client.post(favorite_url)
    favorite_when_added: bool = session_client.get(get_page_url(page, project)).json()["is_favorite"]
    removed: api_response.Response = session_client.delete(favorite_url)

    assert (
        added.status_code,
        favorite_when_added,
        removed.status_code,
        session_client.get(get_page_url(page, project)).json()["is_favorite"],
    ) == (204, True, 204, False)


def test_wiki_page_shows_whether_the_user_has_it_in_favorites(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user)
    other: db_models.Page = page_helpers.create_page(workspace, create_user)

    session_client.post(
        f"/api/workspaces/{workspace.slug}/user-favorites/",
        {"entity_type": "page", "entity_identifier": str(page.id), "project_id": None},
        format="json",
    )

    listed: api_response.Response = session_client.get(get_pages_url(workspace), {"order_by": "created_at"})
    assert listed.json()["results"] == [
        page_helpers.get_page_body(page, is_favorite=True),
        page_helpers.get_page_body(other),
    ]


def test_duplicate_copies_one_wiki_page_next_to_the_original(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    parent: db_models.Page = page_helpers.create_page(workspace, create_user)
    page: db_models.Page = page_helpers.create_page(
        workspace, create_user, parent=parent, name="Guide", description_html="<p>Text</p>", description_binary=b"x"
    )
    page_helpers.create_page(workspace, create_user, parent=page)

    response: api_response.Response = session_client.post(get_page_url(page, action="duplicate/"))

    copy: db_models.Page = db_models.Page.objects.get(pk=response.json()["id"])
    assert (
        response.status_code,
        response.json(),
        (copy.name, copy.parent_id, copy.description_html, copy.description_binary),
        db_models.Page.objects.filter(parent=copy).count(),
    ) == (201, page_helpers.get_page_detail_body(copy), ("Guide (Copy)", parent.id, "<p>Text</p>", None), 0)


def test_project_page_list_returns_the_pages_of_the_project_at_any_depth(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=page)
    nested_twice: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=nested)

    response: api_response.Response = session_client.get(get_pages_url(workspace, project), {"order_by": "created_at"})

    assert (response.status_code, response.json()) == (
        200,
        [get_project_page_body(listed, project) for listed in (page, nested, nested_twice)],
    )


def test_nested_project_page_is_retrieved(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=page)

    response: api_response.Response = session_client.get(get_page_url(nested, project))

    assert (response.status_code, response.json()) == (
        200,
        {**get_project_page_body(nested, project), "description_html": nested.description_html, "issue_ids": []},
    )


def test_nested_project_page_is_created_with_the_access_of_its_parent(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, project, access=PRIVATE)

    response: api_response.Response = session_client.post(
        get_pages_url(workspace, project),
        {"name": "Nested", "access": PUBLIC, "parent_id": str(parent.id)},
        format="json",
    )

    page: db_models.Page = db_models.Page.objects.get(pk=response.json()["id"])
    assert (response.status_code, response.json()["access"], get_placements(page)) == (
        201,
        PRIVATE,
        [(parent.id, PRIVATE, None)],
    )


def test_project_page_is_not_created_under_a_page_of_another_project(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    other_project: db_models.Project = page_helpers.create_project(workspace, create_user)
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, other_project)

    response: api_response.Response = session_client.post(
        get_pages_url(workspace, project), {"name": "Nested", "parent_id": str(parent.id)}, format="json"
    )

    assert (response.status_code, db_models.Page.objects.count()) == (404, 1)


@pytest.mark.parametrize("route", ["access/", ""])
def test_access_change_of_a_project_page_changes_its_nested_pages(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
    route: str,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, access=PUBLIC)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, access=PUBLIC, parent=page)

    if route:
        session_client.post(get_page_url(page, project, route), {"access": PRIVATE}, format="json")
    else:
        session_client.patch(get_page_url(page, project), {"access": PRIVATE}, format="json")

    assert get_placements(page, nested) == [(None, PRIVATE, None), (page.id, PRIVATE, None)]


@pytest.mark.parametrize("parent_key", ["parent_id", "parent"])
def test_nesting_a_project_page_gives_it_and_its_nested_pages_the_access_of_the_parent(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
    parent_key: str,
) -> None:
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, project, access=PRIVATE)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, access=PUBLIC)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, project, access=PUBLIC, parent=page)

    response: api_response.Response = session_client.patch(
        get_page_url(page, project), {parent_key: str(parent.id)}, format="json"
    )

    assert (response.status_code, get_placements(page, nested)) == (
        200,
        [(parent.id, PRIVATE, None), (page.id, PRIVATE, None)],
    )


def test_nested_project_page_is_moved_to_the_top_level(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, project)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, parent=parent)

    response: api_response.Response = session_client.patch(
        get_page_url(page, project), {"parent_id": None}, format="json"
    )

    assert (response.status_code, response.json()["parent_id"], get_placements(page)) == (
        200,
        None,
        [(None, PUBLIC, None)],
    )


def test_nested_page_and_link_pages_blocks_survive_a_description_write(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user)
    html: str = (
        f'<nested-page pageid="{page.id}"></nested-page>'
        f'<link-pages source="created_by" parent_id="{page.id}" creator_ids="{create_user.id}" depth="all">'
        "</link-pages>"
    )

    session_client.patch(get_page_url(page, action="description/"), {"description_html": html}, format="json")

    page.refresh_from_db()
    assert page.description_html == html


def test_wiki_list_is_filtered_by_parent_and_by_creators(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    other_member: db_models.User = page_helpers.create_member(workspace)
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, sort_order=1)
    nested: db_models.Page = page_helpers.create_page(workspace, other_member, parent=parent, sort_order=2)
    page_helpers.create_page(workspace, other_member, parent=nested, sort_order=3)

    by_parent: api_response.Response = session_client.get(get_pages_url(workspace), {"parent_id": str(parent.id)})
    by_creators: api_response.Response = session_client.get(
        get_pages_url(workspace), {"created_by": f"{create_user.id},{uuid.uuid4()}"}
    )

    assert (by_parent.json()["results"], by_creators.json()["results"]) == (
        [page_helpers.get_page_body(nested)],
        [page_helpers.get_page_body(parent)],
    )


@pytest.mark.parametrize("track_visit, visits", [("true", 1), ("false", 0)])
def test_opening_a_wiki_page_records_a_visit_when_asked(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    run_tasks_inline: None,
    track_visit: str,
    visits: int,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user)

    session_client.get(get_page_url(page), {"track_visit": track_visit})

    assert (
        db_models.UserRecentVisit.objects.filter(
            user=create_user, entity_name="page", entity_identifier=page.id, project__isnull=True
        ).count()
        == visits
    )


def test_image_of_a_wiki_page_is_addressed_by_the_workspace_asset_route(
    workspace: db_models.Workspace, create_user: db_models.User
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user)

    asset: db_models.FileAsset = db_models.FileAsset.objects.create(
        workspace=workspace,
        page=page,
        asset="image.png",
        entity_type=db_models.FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
    )

    assert asset.asset_url == f"/api/assets/v2/workspaces/{workspace.slug}/{asset.id}/"


def test_page_is_created_with_a_parent_and_the_collection_the_parent_has(
    workspace: db_models.Workspace, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PUBLIC)
    parent: db_models.Page = page_helpers.create_page(workspace, create_user, collection=collection)

    response: api_response.Response = session_client.post(
        get_pages_url(workspace),
        {"name": "Nested", "parent_id": str(parent.id), "collection_id": str(collection.id)},
        format="json",
    )

    page: db_models.Page = db_models.Page.objects.get(pk=response.json()["id"])
    assert (response.status_code, get_placements(page)) == (201, [(parent.id, PUBLIC, collection.id)])


@pytest.mark.parametrize("parent_key", ["parent_id", "parent"])
def test_project_page_is_not_nested_under_itself_by_an_id_in_upper_case(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
    parent_key: str,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)

    response: api_response.Response = session_client.patch(
        get_page_url(page, project), {parent_key: str(page.id).upper()}, format="json"
    )

    page.refresh_from_db()
    assert (response.status_code, page.parent_id) == (400, None)


def test_project_page_is_not_created_under_an_archived_page(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    parent: db_models.Page = page_helpers.create_page(
        workspace, create_user, project, archived_at=datetime.date.today()
    )

    response: api_response.Response = session_client.post(
        get_pages_url(workspace, project), {"name": "Nested", "parent_id": str(parent.id)}, format="json"
    )

    assert (response.status_code, db_models.Page.objects.count()) == (400, 1)


def test_project_page_is_not_nested_under_an_archived_page(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
) -> None:
    parent: db_models.Page = page_helpers.create_page(
        workspace, create_user, project, archived_at=datetime.date.today()
    )
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)

    response: api_response.Response = session_client.patch(
        get_page_url(page, project), {"parent_id": str(parent.id)}, format="json"
    )

    page.refresh_from_db()
    assert (response.status_code, page.parent_id) == (400, None)


@pytest.mark.parametrize("outside_key, null_key", [("parent", "parent_id"), ("parent_id", "parent")])
def test_project_page_is_not_nested_under_a_page_of_another_project_by_either_name_of_the_parent(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    project: db_models.Project,
    session_client: api_test.APIClient,
    outside_key: str,
    null_key: str,
) -> None:
    other_project: db_models.Project = page_helpers.create_project(workspace, create_user)
    outside: db_models.Page = page_helpers.create_page(workspace, create_user, other_project)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project)

    response: api_response.Response = session_client.patch(
        get_page_url(page, project), {outside_key: str(outside.id), null_key: None}, format="json"
    )

    page.refresh_from_db()
    assert (response.status_code, page.parent_id) == (400, None)


@pytest.mark.parametrize("in_project", [False, True])
def test_description_write_with_the_title_of_the_document_stores_it_as_the_name(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    in_project: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, name="Old")

    response: api_response.Response = session_client.patch(
        get_page_url(page, project, "description/"),
        {"description_html": "<p>Text</p>", "name": "New"},
        format="json",
    )

    page.refresh_from_db()
    assert (response.status_code, page.name, page.description_html) == (200, "New", "<p>Text</p>")


@pytest.fixture
def store_while_a_page_is_written() -> t.Iterator[t.Callable[[db_models.Page, t.Dict[str, t.Any]], None]]:
    """
    Returns a function that arranges another writer: it stores the given columns of the page after the
    next request has read the page and right before that request writes it.
    """
    receivers: t.List[t.Callable[..., None]] = []

    def arrange(page: db_models.Page, columns: t.Dict[str, t.Any]) -> None:
        def store(sender: t.Type[db_models.Page], instance: db_models.Page, **kwargs: t.Any) -> None:
            if instance.pk == page.pk:
                django_signals.pre_save.disconnect(store, sender=db_models.Page)
                db_models.Page.objects.filter(pk=page.pk).update(**columns)

        receivers.append(store)
        django_signals.pre_save.connect(store, sender=db_models.Page)

    yield arrange
    receiver: t.Callable[..., None]
    for receiver in receivers:
        django_signals.pre_save.disconnect(receiver, sender=db_models.Page)


def test_wiki_page_update_keeps_a_description_stored_while_it_was_made(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    store_while_a_page_is_written: t.Callable[[db_models.Page, t.Dict[str, t.Any]], None],
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, description_html="<p>Old</p>")
    store_while_a_page_is_written(page, {"description_html": "<p>Newer</p>"})

    session_client.patch(get_page_url(page), {"color": "#fff"}, format="json")

    page.refresh_from_db()
    assert (page.color, page.description_html) == ("#fff", "<p>Newer</p>")


def test_collection_delete_keeps_a_description_stored_while_its_pages_were_moved(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    store_while_a_page_is_written: t.Callable[[db_models.Page, t.Dict[str, t.Any]], None],
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PRIVATE)
    page: db_models.Page = page_helpers.create_page(
        workspace, create_user, access=PRIVATE, collection=collection, description_html="<p>Old</p>"
    )
    store_while_a_page_is_written(page, {"description_html": "<p>Newer</p>"})

    session_client.delete(f"{get_collections_url(workspace)}{collection.id}/")

    page.refresh_from_db()
    assert (page.collection_id, page.description_html) == (None, "<p>Newer</p>")


@pytest.mark.parametrize("in_project", [False, True])
def test_description_write_keeps_a_color_stored_while_it_was_made(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    store_while_a_page_is_written: t.Callable[[db_models.Page, t.Dict[str, t.Any]], None],
    in_project: bool,
) -> None:
    project: t.Optional[db_models.Project] = page_helpers.create_project(workspace, create_user) if in_project else None
    page: db_models.Page = page_helpers.create_page(workspace, create_user, project, color="#000")
    store_while_a_page_is_written(page, {"color": "#fff"})

    session_client.patch(
        get_page_url(page, project, "description/"), {"description_html": "<p>Text</p>"}, format="json"
    )

    page.refresh_from_db()
    assert (page.description_html, page.color) == ("<p>Text</p>", "#fff")


@pytest.mark.parametrize(
    "change, transactions",
    [({"name": "New"}, 0), ({"description_html": "<p>Old</p>"}, 0), ({"description_html": "<p>New</p>"}, 1)],
)
def test_wiki_page_update_queues_the_page_transaction_only_for_a_changed_description(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    session_client: api_test.APIClient,
    monkeypatch: pytest.MonkeyPatch,
    change: t.Dict[str, str],
    transactions: int,
) -> None:
    page: db_models.Page = page_helpers.create_page(workspace, create_user, description_html="<p>Old</p>")
    queued: t.List[t.Dict[str, t.Any]] = []
    monkeypatch.setattr(page_transaction_task.page_transaction, "delay", lambda **task: queued.append(task))

    session_client.patch(get_page_url(page), change, format="json")

    assert len(queued) == transactions
