# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t
import uuid

import rest_framework.serializers as serializers

import plane.api.serializers.base as base_serializers
import plane.app.serializers as app_serializers
import plane.db.models as db_models


class PageSerializer(base_serializers.BaseSerializer):
    parent_id: serializers.UUIDField = serializers.UUIDField(required=False, allow_null=True)
    collection_id: serializers.UUIDField = serializers.UUIDField(required=False, allow_null=True)
    page_collection_id: serializers.SerializerMethodField = serializers.SerializerMethodField()
    is_favorite: serializers.BooleanField = serializers.BooleanField(read_only=True)

    class Meta:
        model: t.Type[db_models.Page] = db_models.Page
        fields: t.List[str] = [
            "id",
            "name",
            "owned_by",
            "workspace",
            "access",
            "color",
            "is_locked",
            "archived_at",
            "is_global",
            "parent_id",
            "collection_id",
            "page_collection_id",
            "sort_order",
            "is_favorite",
            "view_props",
            "logo_props",
            "external_id",
            "external_source",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields: t.List[str] = ["workspace", "owned_by", "archived_at", "is_global"]

    def get_page_collection_id(self, page: db_models.Page) -> t.Optional[uuid.UUID]:
        # The SDK addresses a page inside a collection by the id of a membership row. A page is in
        # one collection at most, so its own id serves as that id.
        return page.id if page.collection_id else None

    def update(self, page: db_models.Page, validated_data: t.Dict[str, t.Any]) -> db_models.Page:
        field: str
        value: t.Any
        for field, value in validated_data.items():
            setattr(page, field, value)
        # Only the written columns: the page was read before other writes of it, and the live server
        # stores the description and the name of an open page at any moment.
        update_fields: t.List[str] = [*validated_data, "updated_at", "updated_by"]
        if "description_html" in validated_data:
            update_fields.append("description_stripped")
        page.save(update_fields=update_fields)
        return page


class PageDetailSerializer(PageSerializer):
    description_html: serializers.CharField = serializers.CharField(required=False)

    class Meta(PageSerializer.Meta):
        fields: t.List[str] = PageSerializer.Meta.fields + ["description_html"]

    validate_description_html: t.Callable[[serializers.Serializer, str], str] = (
        app_serializers.PageBinaryUpdateSerializer.validate_description_html
    )


class PageLiteSerializer(base_serializers.BaseSerializer):
    class Meta:
        model: t.Type[db_models.Page] = db_models.Page
        fields: t.List[str] = ["id", "name", "logo_props"]


class CollectionSerializer(base_serializers.BaseSerializer):
    class Meta:
        model: t.Type[db_models.Collection] = db_models.Collection
        fields: t.List[str] = [
            "id",
            "name",
            "access",
            "owned_by_id",
            "is_default",
            "logo_props",
            "sort_order",
            "workspace",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields: t.List[str] = ["workspace", "is_default"]

    def validate_access(self, value: int) -> int:
        # The pages of a collection copy its access.
        if self.instance and value != self.instance.access:
            raise serializers.ValidationError("The access of a collection cannot be changed.")
        return value


class CollectionPageSerializer(base_serializers.BaseSerializer):
    """A page as the SDK's page-collection membership record. See PageSerializer.page_collection_id."""

    page: serializers.UUIDField = serializers.UUIDField(source="id")

    class Meta:
        model: t.Type[db_models.Page] = db_models.Page
        fields: t.List[str] = [
            "id",
            "collection",
            "page",
            "workspace",
            "sort_order",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class CollectionBranchPageSerializer(serializers.ModelSerializer):
    page_collection_id: serializers.UUIDField = serializers.UUIDField(source="id")
    page: PageSerializer = PageSerializer(source="*")

    class Meta:
        model: t.Type[db_models.Page] = db_models.Page
        fields: t.List[str] = ["page_collection_id", "collection_id", "parent_id", "sort_order", "page"]


class CollectionPageAddSerializer(serializers.Serializer):
    page_ids: serializers.ListField = serializers.ListField(child=serializers.UUIDField())


class CollectionPageUpdateSerializer(serializers.Serializer):
    collection: serializers.UUIDField = serializers.UUIDField(required=False)
    sort_order: serializers.FloatField = serializers.FloatField(required=False)
