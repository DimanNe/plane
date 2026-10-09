# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import rest_framework.serializers as api_serializers

import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties


class ProjectFeatureSerializer(custom_properties.ProjectTypesSerializerMixin, api_serializers.ModelSerializer):
    """The feature switches of a project under the names the SDK gives them."""

    modules = api_serializers.BooleanField(source="module_view", required=False)
    cycles = api_serializers.BooleanField(source="cycle_view", required=False)
    views = api_serializers.BooleanField(source="issue_views_view", required=False)
    pages = api_serializers.BooleanField(source="page_view", required=False)
    intakes = api_serializers.BooleanField(source="intake_view", required=False)
    milestones = api_serializers.BooleanField(source="milestone_view", required=False)
    work_item_types = api_serializers.BooleanField(source="is_issue_type_enabled", required=False)

    class Meta:
        model = db_models.Project
        fields = ["modules", "cycles", "views", "pages", "intakes", "milestones", "work_item_types"]


class WorkspaceFeatureSerializer(api_serializers.ModelSerializer):
    wiki = api_serializers.BooleanField(source="is_wiki_enabled", required=False)

    class Meta:
        model = db_models.Workspace
        fields = ["wiki"]
