# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The collection endpoints of /api/v1/ that plane-sdk calls (plane/api/collections), members excepted."""

import typing as t
import uuid

import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.db.models as db_models
import plane.tests.contract.page_helpers as page_helpers

pytestmark = [pytest.mark.django_db, pytest.mark.contract]

PUBLIC: int = db_models.Page.PUBLIC_ACCESS
PRIVATE: int = db_models.Page.PRIVATE_ACCESS


def get_collections_url(workspace: db_models.Workspace) -> str:
    return f"/api/v1/workspaces/{workspace.slug}/collections/"


def get_collection_url(collection: db_models.Collection, action: str = "") -> str:
    return f"{get_collections_url(collection.workspace)}{collection.id}/{action}"


def create_collection(
    workspace: db_models.Workspace, owner: db_models.User, access: int = PUBLIC, **fields: t.Any
) -> db_models.Collection:
    return db_models.Collection.objects.create(
        workspace=workspace, owned_by=owner, access=access, **{"name": "Handbook", **fields}
    )


def get_membership_body(page: db_models.Page) -> t.Dict[str, t.Any]:
    """A page as the SDK's record of its membership in a collection."""
    return {
        "id": str(page.id),
        "collection": page_helpers.get_id(page.collection_id),
        "page": str(page.id),
        "workspace": str(page.workspace_id),
        "sort_order": page.sort_order,
        "created_at": page_helpers.get_time(page.created_at),
        "updated_at": page_helpers.get_time(page.updated_at),
        "created_by": page_helpers.get_id(page.created_by_id),
        "updated_by": page_helpers.get_id(page.updated_by_id),
    }


def get_placements(*pages: db_models.Page) -> t.List[t.Tuple[int, t.Optional[uuid.UUID], bool]]:
    """The access and the collection of each page, and whether it is archived, as stored."""
    placements: t.List[t.Tuple[int, t.Optional[uuid.UUID], bool]] = []
    page: db_models.Page
    for page in pages:
        page.refresh_from_db()
        placements.append((page.access, page.collection_id, page.archived_at is not None))
    return placements


def test_list_returns_the_public_collections_and_the_private_ones_of_the_user(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    other_member: db_models.User = page_helpers.create_member(workspace)
    public: db_models.Collection = create_collection(workspace, other_member, PUBLIC, sort_order=1)
    private: db_models.Collection = create_collection(workspace, create_user, PRIVATE, sort_order=2)
    create_collection(workspace, other_member, PRIVATE, sort_order=3)

    response: api_response.Response = api_key_client.get(get_collections_url(workspace))

    assert (response.status_code, response.json()) == (
        200,
        [page_helpers.get_collection_body(public), page_helpers.get_collection_body(private)],
    )


def test_create_returns_the_new_collection_owned_by_the_user(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    response: api_response.Response = api_key_client.post(
        get_collections_url(workspace), {"name": "Handbook", "access": PRIVATE}, format="json"
    )

    collection: db_models.Collection = db_models.Collection.objects.get(pk=response.json()["id"])
    assert (
        response.status_code,
        response.json(),
        (collection.name, collection.access, collection.owned_by_id, collection.is_default),
    ) == (201, page_helpers.get_collection_body(collection), ("Handbook", PRIVATE, create_user.id, False))


def test_retrieve_returns_the_collection(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user)

    response: api_response.Response = api_key_client.get(get_collection_url(collection))

    assert (response.status_code, response.json()) == (200, page_helpers.get_collection_body(collection))


def test_private_collection_of_another_member_is_not_served(
    workspace: db_models.Workspace, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, page_helpers.create_member(workspace), PRIVATE)

    response: api_response.Response = api_key_client.get(get_collection_url(collection))

    assert response.status_code == 404


def test_update_changes_the_name_and_the_sort_order(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user)

    response: api_response.Response = api_key_client.patch(
        get_collection_url(collection), {"name": "Guides", "sort_order": 5}, format="json"
    )

    collection.refresh_from_db()
    assert (response.status_code, response.json(), collection.name, collection.sort_order) == (
        200,
        page_helpers.get_collection_body(collection),
        "Guides",
        5,
    )


def test_update_does_not_change_the_access(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PUBLIC)

    response: api_response.Response = api_key_client.patch(
        get_collection_url(collection), {"access": PRIVATE}, format="json"
    )

    collection.refresh_from_db()
    assert (response.status_code, collection.access) == (400, PUBLIC)


def test_default_collection_is_not_deleted(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, is_default=True)

    response: api_response.Response = api_key_client.delete(get_collection_url(collection))

    assert (response.status_code, db_models.Collection.objects.filter(pk=collection.id).exists()) == (400, True)


def test_collection_is_deleted_by_its_owner_or_an_admin_only(
    workspace: db_models.Workspace, create_user: db_models.User
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user)
    other_member: api_test.APIClient = page_helpers.get_client(page_helpers.create_member(workspace))

    response: api_response.Response = other_member.delete(
        f"/api/workspaces/{workspace.slug}/collections/{collection.id}/"
    )

    assert (response.status_code, db_models.Collection.objects.filter(pk=collection.id).exists()) == (403, True)


@pytest.mark.parametrize(
    "access, archive_pages, expected_access, is_filed_in_default, is_archived",
    [
        (PUBLIC, None, PUBLIC, True, True),
        (PUBLIC, "true", PUBLIC, True, True),
        (PUBLIC, "false", PUBLIC, True, False),
        (PRIVATE, None, PRIVATE, False, True),
        (PRIVATE, "false", PRIVATE, False, True),
    ],
)
def test_delete_keeps_the_pages_archives_them_unless_told_not_to_and_refiles_the_public_ones(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    api_key_client: api_test.APIClient,
    access: int,
    archive_pages: t.Optional[str],
    expected_access: int,
    is_filed_in_default: bool,
    is_archived: bool,
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, access)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=access, collection=collection)
    nested: db_models.Page = page_helpers.create_page(
        workspace, create_user, access=access, collection=collection, parent=page
    )

    response: api_response.Response = api_key_client.delete(
        get_collection_url(collection) + (f"?archive_pages={archive_pages}" if archive_pages else "")
    )

    default: t.Optional[db_models.Collection] = db_models.Collection.objects.filter(is_default=True).first()
    expected_collection: t.Optional[uuid.UUID] = default.id if default and is_filed_in_default else None
    assert (
        response.status_code,
        db_models.Collection.objects.filter(pk=collection.id).exists(),
        get_placements(page, nested),
    ) == (204, False, [(expected_access, expected_collection, is_archived)] * 2)


def test_pages_lists_the_top_level_pages_of_the_collection(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, collection=collection)
    page_helpers.create_page(workspace, create_user, collection=collection, parent=page)
    page_helpers.create_page(workspace, create_user, collection=create_collection(workspace, create_user))

    response: api_response.Response = api_key_client.get(get_collection_url(collection, "pages/"))

    assert (response.status_code, response.json()["results"]) == (
        200,
        [
            {
                "page_collection_id": str(page.id),
                "collection_id": str(collection.id),
                "parent_id": None,
                "sort_order": page.sort_order,
                "page": page_helpers.get_page_body(page),
            }
        ],
    )


def test_pages_is_filtered_by_parent_and_by_name(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, collection=collection, name="Handbook")
    nested: db_models.Page = page_helpers.create_page(
        workspace, create_user, collection=collection, parent=page, name="Runbook"
    )
    page_helpers.create_page(workspace, create_user, collection=collection, name="Policies")

    by_parent: api_response.Response = api_key_client.get(
        get_collection_url(collection, "pages/"), {"parent_id": str(page.id)}
    )
    by_name: api_response.Response = api_key_client.get(get_collection_url(collection, "pages/"), {"search": "handb"})

    assert (
        [row["page_collection_id"] for row in by_parent.json()["results"]],
        [row["page_collection_id"] for row in by_name.json()["results"]],
    ) == ([str(nested.id)], [str(page.id)])


def test_pages_search_returns_the_top_level_pages_outside_the_collection(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user)
    page_helpers.create_page(workspace, create_user, collection=collection, name="Guide inside")
    outside: db_models.Page = page_helpers.create_page(workspace, create_user, name="Guide outside")
    page_helpers.create_page(workspace, create_user, name="Guide nested", parent=outside)
    page_helpers.create_page(workspace, create_user, name="Policy outside")

    response: api_response.Response = api_key_client.get(
        get_collection_url(collection, "pages-search/"), {"search": "guide"}
    )

    assert (response.status_code, response.json()) == (
        200,
        [{"id": str(outside.id), "name": "Guide outside", "logo_props": {}}],
    )


def test_adding_a_page_files_it_and_its_nested_pages_with_the_access_of_the_collection(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PRIVATE)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC)
    nested: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC, parent=page)

    response: api_response.Response = api_key_client.post(
        get_collection_url(collection, "pages/"), {"page_ids": [str(page.id), str(nested.id)]}, format="json"
    )

    placements: t.List[t.Tuple[int, t.Optional[uuid.UUID], bool]] = get_placements(page, nested)
    # the nested page is filed by its parent, so it has no membership of its own
    assert (response.status_code, response.json(), placements) == (
        201,
        [get_membership_body(page)],
        [(PRIVATE, collection.id, False)] * 2,
    )


def test_updating_a_page_of_a_collection_moves_it_to_another_collection_and_orders_it(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, PUBLIC)
    target: db_models.Collection = create_collection(workspace, create_user, PRIVATE)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=PUBLIC, collection=collection)

    response: api_response.Response = api_key_client.patch(
        get_collection_url(collection, f"pages/{page.id}/"),
        {"collection": str(target.id), "sort_order": 7},
        format="json",
    )

    placements: t.List[t.Tuple[int, t.Optional[uuid.UUID], bool]] = get_placements(page)
    assert (response.status_code, response.json(), placements, page.sort_order) == (
        200,
        get_membership_body(page),
        [(PRIVATE, target.id, False)],
        7,
    )


@pytest.mark.parametrize("access", [PUBLIC, PRIVATE])
def test_removing_a_page_refiles_a_public_page_in_the_default_collection_and_leaves_a_private_one_unfiled(
    workspace: db_models.Workspace,
    create_user: db_models.User,
    api_key_client: api_test.APIClient,
    access: int,
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user, access)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, access=access, collection=collection)

    response: api_response.Response = api_key_client.delete(get_collection_url(collection, f"pages/{page.id}/"))

    default: t.Optional[db_models.Collection] = db_models.Collection.objects.filter(is_default=True).first()
    assert (response.status_code, get_placements(page)) == (
        204,
        [(access, default.id if default else None, False)],
    )
    assert (default is not None) == (access == PUBLIC)


def test_page_is_addressed_through_the_collection_it_is_in(
    workspace: db_models.Workspace, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    collection: db_models.Collection = create_collection(workspace, create_user)
    other: db_models.Collection = create_collection(workspace, create_user)
    page: db_models.Page = page_helpers.create_page(workspace, create_user, collection=collection)

    response: api_response.Response = api_key_client.delete(get_collection_url(other, f"pages/{page.id}/"))

    assert (response.status_code, get_placements(page)) == (404, [(PUBLIC, collection.id, False)])
