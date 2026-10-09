# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import typing as t
import uuid

import django.core.serializers.json as django_json
import django.db.models as django_models
import django.db.transaction as django_transaction
import django.utils.timezone as django_timezone
import rest_framework.request as api_request
import rest_framework.response as api_response
import rest_framework.serializers as api_serializers
import rest_framework.status as api_status

import plane.app.permissions as app_permissions
import plane.app.serializers.milestone as milestone_serializers
import plane.app.views.base as base_views
import plane.bgtasks.issue_activities_task as issue_activities_task
import plane.db.models as db_models
import plane.utils.host as host


class MilestoneViewSetMixin:
    """Milestone handlers of both `/api/` and `/api/v1/`; the two differ only in the base view set they add."""

    serializer_class = milestone_serializers.MilestoneSerializer
    permission_classes = [app_permissions.ProjectEntityPermission]

    def get_queryset(self) -> django_models.QuerySet[db_models.Milestone]:
        linked: django_models.Q = django_models.Q(
            issues__archived_at__isnull=True, issues__is_draft=False, issues__deleted_at__isnull=True
        )
        return db_models.Milestone.objects.filter(
            workspace__slug=self.kwargs["slug"], project_id=self.kwargs["project_id"]
        ).annotate(
            total_issues=django_models.Count("issues", filter=linked),
            completed_issues=django_models.Count(
                "issues", filter=linked & django_models.Q(issues__state__group="completed")
            ),
            cancelled_issues=django_models.Count(
                "issues", filter=linked & django_models.Q(issues__state__group="cancelled")
            ),
        )

    def get_serializer_context(self) -> t.Dict[str, object]:
        return {**super().get_serializer_context(), "project_id": self.kwargs["project_id"]}

    def get_requested_issue_ids(self) -> t.List[uuid.UUID]:
        serializer: milestone_serializers.MilestoneIssueRequestSerializer = (
            milestone_serializers.MilestoneIssueRequestSerializer(data=self.request.data)
        )
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["issues"]

    def set_milestone_of_issues(
        self, issues: django_models.QuerySet[db_models.Issue], milestone_id: t.Optional[uuid.UUID]
    ) -> None:
        """Link the work items to the milestone, or unlink them when it is None, and record the change on each."""
        issue_id: uuid.UUID
        previous_milestone_id: t.Optional[uuid.UUID]
        moved: t.List[t.Tuple[uuid.UUID, t.Optional[uuid.UUID]]] = list(
            issues.exclude(milestone_id=milestone_id).values_list("id", "milestone_id")
        )
        db_models.Issue.objects.filter(pk__in=[issue_id for issue_id, _ in moved]).update(milestone_id=milestone_id)
        for issue_id, previous_milestone_id in moved:
            issue_activities_task.issue_activity.delay(
                type="issue.activity.updated",
                requested_data=json.dumps({"milestone_id": milestone_id}, cls=django_json.DjangoJSONEncoder),
                current_instance=json.dumps({"milestone_id": previous_milestone_id}, cls=django_json.DjangoJSONEncoder),
                issue_id=str(issue_id),
                actor_id=str(self.request.user.id),
                project_id=str(self.kwargs["project_id"]),
                epoch=int(django_timezone.now().timestamp()),
                notification=True,
                origin=host.base_host(request=self.request, is_app=True),
            )

    def list(self, request: api_request.Request, slug: str, project_id: uuid.UUID) -> api_response.Response:
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            order_by="target_date",
            on_results=lambda milestones: milestone_serializers.MilestoneSerializer(milestones, many=True).data,
        )

    def perform_create(self, serializer: milestone_serializers.MilestoneSerializer) -> None:
        serializer.save(project_id=self.kwargs["project_id"])

    def perform_destroy(self, milestone: db_models.Milestone) -> None:
        with django_transaction.atomic():
            self.set_milestone_of_issues(milestone.issues.all(), None)
            milestone.delete()

    def list_work_items(
        self, request: api_request.Request, slug: str, project_id: uuid.UUID, milestone_id: uuid.UUID
    ) -> api_response.Response:
        return self.paginate(
            request=request,
            queryset=db_models.Issue.issue_objects.filter(
                workspace__slug=slug, project_id=project_id, milestone_id=milestone_id
            ),
            on_results=lambda issues: milestone_serializers.MilestoneIssueSerializer(issues, many=True).data,
        )

    def add_work_items(
        self, request: api_request.Request, slug: str, project_id: uuid.UUID, milestone_id: uuid.UUID
    ) -> api_response.Response:
        milestone: db_models.Milestone = self.get_queryset().get(pk=milestone_id)
        issue_ids: t.List[uuid.UUID] = self.get_requested_issue_ids()
        issues: django_models.QuerySet[db_models.Issue] = db_models.Issue.issue_objects.filter(
            workspace__slug=slug, project_id=project_id, pk__in=issue_ids
        )
        if issues.count() != len(set(issue_ids)):
            raise api_serializers.ValidationError({"issues": "Every work item must be in the project of the milestone"})
        self.set_milestone_of_issues(issues, milestone.id)
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)

    def remove_work_items(
        self, request: api_request.Request, slug: str, project_id: uuid.UUID, milestone_id: uuid.UUID
    ) -> api_response.Response:
        self.set_milestone_of_issues(
            db_models.Issue.objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                milestone_id=milestone_id,
                pk__in=self.get_requested_issue_ids(),
            ),
            None,
        )
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)


class MilestoneViewSet(MilestoneViewSetMixin, base_views.BaseViewSet):
    pass
