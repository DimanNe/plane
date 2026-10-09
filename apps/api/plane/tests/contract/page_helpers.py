# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What the page tests of the web app API and of /api/v1/ share: records to act on and expected bodies."""

import datetime
import typing as t
import uuid

import rest_framework.test as api_test

import plane.db.models as db_models


def create_project(workspace: db_models.Workspace, admin: db_models.User) -> db_models.Project:
    identifier: str = uuid.uuid4().hex[:6].upper()
    project: db_models.Project = db_models.Project.objects.create(
        name=f"Project {identifier}", identifier=identifier, workspace=workspace
    )
    db_models.ProjectMember.objects.create(workspace=workspace, project=project, member=admin, role=20)
    return project


def create_member(workspace: db_models.Workspace, role: int = 15) -> db_models.User:
    name: str = uuid.uuid4().hex
    user: db_models.User = db_models.User.objects.create(email=f"{name}@plane.so", username=name)
    db_models.WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def get_client(user: db_models.User) -> api_test.APIClient:
    client: api_test.APIClient = api_test.APIClient()
    client.force_authenticate(user=user)
    return client


def create_page(
    workspace: db_models.Workspace,
    owner: db_models.User,
    project: t.Optional[db_models.Project] = None,
    **fields: t.Any,
) -> db_models.Page:
    page: db_models.Page = db_models.Page(workspace=workspace, owned_by=owner, is_global=project is None, **fields)
    page.save(created_by_id=owner.id)
    if project:
        db_models.ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return page


def get_time(value: datetime.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def get_id(value: t.Optional[uuid.UUID]) -> t.Optional[str]:
    return str(value) if value else None


def get_page_body(page: db_models.Page, is_favorite: bool = False) -> t.Dict[str, t.Any]:
    return {
        "id": str(page.id),
        "name": page.name,
        "owned_by": str(page.owned_by_id),
        "workspace": str(page.workspace_id),
        "access": page.access,
        "color": page.color,
        "is_locked": page.is_locked,
        "archived_at": page.archived_at.isoformat() if page.archived_at else None,
        "is_global": page.is_global,
        "parent_id": get_id(page.parent_id),
        "collection_id": get_id(page.collection_id),
        "page_collection_id": str(page.id) if page.collection_id else None,
        "sort_order": page.sort_order,
        "is_favorite": is_favorite,
        "view_props": page.view_props,
        "logo_props": page.logo_props,
        "external_id": page.external_id,
        "external_source": page.external_source,
        "created_at": get_time(page.created_at),
        "updated_at": get_time(page.updated_at),
        "created_by": get_id(page.created_by_id),
        "updated_by": get_id(page.updated_by_id),
    }


def get_page_detail_body(page: db_models.Page) -> t.Dict[str, t.Any]:
    return {**get_page_body(page), "description_html": page.description_html}


def get_collection_body(collection: db_models.Collection) -> t.Dict[str, t.Any]:
    return {
        "id": str(collection.id),
        "name": collection.name,
        "access": collection.access,
        "owned_by_id": str(collection.owned_by_id),
        "is_default": collection.is_default,
        "logo_props": collection.logo_props,
        "sort_order": collection.sort_order,
        "workspace": str(collection.workspace_id),
        "created_at": get_time(collection.created_at),
        "updated_at": get_time(collection.updated_at),
        "created_by": get_id(collection.created_by_id),
        "updated_by": get_id(collection.updated_by_id),
    }
