# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t
import uuid

import django.db as django_db
import django.db.backends.utils as django_db_utils

import plane.db.models as db_models


def get_nested_page_ids(page_id: uuid.UUID) -> t.List[uuid.UUID]:
    cursor: django_db_utils.CursorWrapper
    with django_db.connection.cursor() as cursor:
        cursor.execute(
            """
            WITH RECURSIVE nested AS (
                SELECT id FROM pages WHERE parent_id = %s AND deleted_at IS NULL
                UNION
                SELECT pages.id FROM pages, nested WHERE pages.parent_id = nested.id AND pages.deleted_at IS NULL
            )
            SELECT id FROM nested
            """,
            [page_id],
        )
        return [row[0] for row in cursor.fetchall()]


def place_page(
    page: db_models.Page, parent: t.Optional[db_models.Page], collection: t.Optional[db_models.Collection]
) -> None:
    """
    Saves the page under the parent or in the collection. A nested page has the access and the
    collection of its parent and a page in a collection has the access of the collection, so the
    pages nested under the page change with it. A public wiki page is always in a collection.
    """
    if parent:
        page.access = parent.access
        collection = parent.collection
    elif collection:
        page.access = collection.access
    elif page.is_global and page.access == db_models.Page.PUBLIC_ACCESS:
        collection = db_models.Collection.objects.get_or_create(
            workspace_id=page.workspace_id,
            is_default=True,
            defaults={"name": "General", "owned_by_id": page.owned_by_id},
        )[0]
    page.parent = parent
    page.collection = collection
    # Only these columns: the page was read before this request's other writes and before live's stores of it.
    page.save(update_fields=["parent", "collection", "access", "updated_at", "updated_by"])
    db_models.Page.objects.filter(id__in=get_nested_page_ids(page.id)).update(access=page.access, collection=collection)
