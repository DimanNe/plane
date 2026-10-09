# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.db.models as django_models
import rest_framework.serializers as api_serializers

import plane.app.serializers.base as base_serializers
import plane.db.models as db_models
import plane.utils.content_validator as content_validator


class MilestoneSerializer(base_serializers.BaseSerializer):
    # Annotated by the milestone views; a milestone that was just created has no work items.
    total_issues = api_serializers.IntegerField(read_only=True, default=0)
    completed_issues = api_serializers.IntegerField(read_only=True, default=0)
    cancelled_issues = api_serializers.IntegerField(read_only=True, default=0)

    def validate_title(self, title: str) -> str:
        milestones: django_models.QuerySet[db_models.Milestone] = db_models.Milestone.objects.filter(
            project_id=self.context["project_id"], title=title
        )
        if self.instance is not None:
            milestones = milestones.exclude(pk=self.instance.pk)
        if milestones.exists():
            raise api_serializers.ValidationError("Milestone with the same title already exists in the project")
        return title

    def validate_description_html(self, description_html: str) -> str:
        is_valid: bool
        sanitized_html: t.Optional[str]
        is_valid, _, sanitized_html = content_validator.validate_html_content(description_html)
        if not is_valid:
            raise api_serializers.ValidationError("html content is not valid")
        return description_html if sanitized_html is None else sanitized_html

    class Meta:
        model = db_models.Milestone
        fields = "__all__"
        read_only_fields = ["workspace", "project", "created_by", "updated_by", "deleted_at"]


class MilestoneIssueSerializer(base_serializers.BaseSerializer):
    # The SDK reads a link between a milestone and a work item with an id of its own; here the link is the
    # milestone column of the work item, so both ids are the work item's.
    issue = api_serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = db_models.Issue
        fields = ["id", "issue", "milestone"]
        read_only_fields = fields


class MilestoneIssueRequestSerializer(api_serializers.Serializer):
    issues = api_serializers.ListField(child=api_serializers.UUIDField(), allow_empty=False)
