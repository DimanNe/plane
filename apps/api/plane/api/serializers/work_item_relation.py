# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import rest_framework.serializers as api_serializers

import plane.db.models as db_models

DEPENDENCY_RELATION_TYPES: t.Tuple[str, ...] = (
    "blocking",
    "blocked_by",
    "start_before",
    "start_after",
    "finish_before",
    "finish_after",
)


class WorkItemDependencyCreateSerializer(api_serializers.ModelSerializer):
    relation_type = api_serializers.ChoiceField(choices=DEPENDENCY_RELATION_TYPES)
    work_item_ids = api_serializers.ListField(child=api_serializers.UUIDField(), allow_empty=False)

    class Meta:
        model = db_models.IssueRelation
        fields = ["relation_type", "work_item_ids", "delay"]
