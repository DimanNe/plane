# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import typing as t
import uuid

import django.core.serializers.json as django_json
import django.db.models as django_models
import django.utils.timezone as django_timezone
import rest_framework.request as api_request
import rest_framework.response as api_response
import rest_framework.serializers as api_serializers
import rest_framework.status as api_status

import plane.api.serializers.work_item_relation as relation_serializers
import plane.api.views.base as base_views
import plane.app.permissions as app_permissions
import plane.bgtasks.issue_activities_task as issue_activities_task
import plane.db.models as db_models
import plane.utils.host as host
import plane.utils.issue_relation_mapper as issue_relation_mapper
import plane.utils.timeline_dependencies as timeline_dependencies

OTHER_RELATION_TYPES: t.Tuple[str, ...] = ("relates_to", "duplicate", "implements", "implemented_by")


def read_relation_type(relation_type: str, source_id: uuid.UUID, issue_id: uuid.UUID) -> str:
    """A relation is stored from one of its two work items; from the other one it reads as the inverse type."""
    return relation_type if source_id == issue_id else issue_relation_mapper.get_inverse_relation(relation_type)


def get_related_work_items(
    slug: str, issue_id: uuid.UUID, relation_types: t.Iterable[str]
) -> t.Dict[str, t.List[t.Dict[str, object]]]:
    """Work items related to the given one, grouped by the relation type as read from the given one."""
    related_ids: t.Dict[str, t.List[uuid.UUID]] = {relation_type: [] for relation_type in relation_types}
    relation_type: str
    source_id: uuid.UUID
    related_id: uuid.UUID
    for relation_type, source_id, related_id in db_models.IssueRelation.objects.filter(
        django_models.Q(issue_id=issue_id) | django_models.Q(related_issue_id=issue_id), workspace__slug=slug
    ).values_list("relation_type", "issue_id", "related_issue_id"):
        relation_type = read_relation_type(relation_type, source_id, issue_id)
        if relation_type in related_ids:
            related_ids[relation_type].append(related_id if source_id == issue_id else source_id)
    work_items: t.Dict[uuid.UUID, t.Dict[str, object]] = {
        work_item["id"]: work_item
        for work_item in db_models.Issue.issue_objects.filter(
            pk__in=[related_id for ids in related_ids.values() for related_id in ids]
        ).values(
            "id",
            "name",
            "sequence_id",
            "project_id",
            "state_id",
            "priority",
            "type_id",
            "sort_order",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )
    }
    return {
        relation_type: [
            {**work_items[related_id], "relation_type": relation_type} for related_id in ids if related_id in work_items
        ]
        for relation_type, ids in related_ids.items()
    }


class WorkItemDependencyListCreateAPIEndpoint(base_views.BaseAPIView):
    permission_classes = [app_permissions.ProjectEntityPermission]

    def get(
        self, request: api_request.Request, slug: str, project_id: uuid.UUID, issue_id: uuid.UUID
    ) -> api_response.Response:
        return api_response.Response(
            get_related_work_items(slug, issue_id, relation_serializers.DEPENDENCY_RELATION_TYPES)
        )

    def post(
        self, request: api_request.Request, slug: str, project_id: uuid.UUID, issue_id: uuid.UUID
    ) -> api_response.Response:
        serializer: relation_serializers.WorkItemDependencyCreateSerializer = (
            relation_serializers.WorkItemDependencyCreateSerializer(data=request.data)
        )
        serializer.is_valid(raise_exception=True)
        relation_type: str = serializer.validated_data["relation_type"]
        work_item_ids: t.List[uuid.UUID] = serializer.validated_data["work_item_ids"]
        if db_models.Issue.issue_objects.filter(workspace__slug=slug, pk__in=work_item_ids).count() != len(
            set(work_item_ids)
        ):
            raise api_serializers.ValidationError(
                {"work_item_ids": "Every work item must be in the workspace and not archived"}
            )
        project: db_models.Project = db_models.Project.objects.get(pk=project_id, workspace__slug=slug)
        timeline_dependencies.create_issue_relations(project, issue_id, work_item_ids, relation_type, request.user)
        issue_activities_task.issue_activity.delay(
            type="issue_relation.activity.created",
            requested_data=json.dumps(
                {"relation_type": relation_type, "issues": work_item_ids}, cls=django_json.DjangoJSONEncoder
            ),
            actor_id=str(request.user.id),
            issue_id=str(issue_id),
            project_id=str(project_id),
            current_instance=None,
            epoch=int(django_timezone.now().timestamp()),
            notification=True,
            origin=host.base_host(request=request, is_app=True),
        )
        return api_response.Response(
            [
                work_item
                for work_item in get_related_work_items(slug, issue_id, [relation_type])[relation_type]
                if work_item["id"] in work_item_ids
            ],
            status=api_status.HTTP_201_CREATED,
        )


class WorkItemDependencyDetailAPIEndpoint(base_views.BaseAPIView):
    permission_classes = [app_permissions.ProjectEntityPermission]

    def delete(
        self,
        request: api_request.Request,
        slug: str,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        related_issue_id: uuid.UUID,
    ) -> api_response.Response:
        issue_relation: t.Optional[db_models.IssueRelation] = db_models.IssueRelation.objects.filter(
            django_models.Q(issue_id=issue_id, related_issue_id=related_issue_id)
            | django_models.Q(issue_id=related_issue_id, related_issue_id=issue_id),
            workspace__slug=slug,
            relation_type__in=timeline_dependencies.DEPENDENCY_TYPES,
        ).first()
        if issue_relation is None:
            return api_response.Response(
                {"error": "These work items have no dependency"}, status=api_status.HTTP_404_NOT_FOUND
            )
        issue_relation.delete()
        issue_activities_task.issue_activity.delay(
            type="issue_relation.activity.deleted",
            requested_data=json.dumps(
                {
                    "related_issue": related_issue_id,
                    "relation_type": read_relation_type(
                        issue_relation.relation_type, issue_relation.issue_id, issue_id
                    ),
                },
                cls=django_json.DjangoJSONEncoder,
            ),
            actor_id=str(request.user.id),
            issue_id=str(issue_id),
            project_id=str(project_id),
            current_instance=None,
            epoch=int(django_timezone.now().timestamp()),
            notification=True,
            origin=host.base_host(request=request, is_app=True),
        )
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)


class WorkItemRelationListAPIEndpoint(base_views.BaseAPIView):
    """Relations other than dependencies, under the path where the SDK lists relations of workspace-defined types."""

    permission_classes = [app_permissions.ProjectEntityPermission]

    def get(
        self, request: api_request.Request, slug: str, project_id: uuid.UUID, issue_id: uuid.UUID
    ) -> api_response.Response:
        return api_response.Response(get_related_work_items(slug, issue_id, OTHER_RELATION_TYPES))


class WorkItemRelationDefinitionListAPIEndpoint(base_views.BaseAPIView):
    """This edition has no workspace-defined relation types; the SDK reads the list before it lists or creates
    relations, so the list exists and is empty."""

    permission_classes = [app_permissions.WorkspaceUserPermission]

    def get(self, request: api_request.Request, slug: str) -> api_response.Response:
        return self.paginate(request=request, queryset=db_models.IssueRelation.objects.none())
