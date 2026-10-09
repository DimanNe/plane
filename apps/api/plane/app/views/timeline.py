# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t
import uuid

import django.db.models as django_models
import rest_framework.request as api_request
import rest_framework.response as api_response

import plane.app.permissions as app_permissions
import plane.app.views.base as base_views
import plane.db.models as db_models
import plane.utils.timeline_dependencies as timeline_dependencies


class TimelineDependenciesEndpoint(base_views.BaseAPIView):
    permission_classes = [app_permissions.ProjectEntityPermission]

    def get(self, request: api_request.Request, slug: str, project_id: uuid.UUID) -> api_response.Response:
        """Dependencies with at least one end in the project, and the work items at their ends: the timeline
        draws a dependency even when its other work item is in another project or filtered out of the layout.
        `relation_type` reads from the predecessor: blocking, start_before or finish_before."""
        relations: t.List[t.Tuple[uuid.UUID, str, uuid.UUID, uuid.UUID]] = list(
            db_models.IssueRelation.objects.filter(
                django_models.Q(issue__project_id=project_id) | django_models.Q(related_issue__project_id=project_id),
                workspace__slug=slug,
                relation_type__in=timeline_dependencies.DEPENDENCY_TYPES,
            ).values_list("id", "relation_type", "issue_id", "related_issue_id")
        )
        relation_id: uuid.UUID
        relation_type: str
        issue_id: uuid.UUID
        related_issue_id: uuid.UUID
        issues: t.Dict[uuid.UUID, t.Dict[str, object]] = {
            issue["id"]: issue
            for issue in db_models.Issue.issue_objects.filter(
                pk__in=[issue_id for _, _, issue_id, _ in relations]
                + [related_issue_id for _, _, _, related_issue_id in relations]
            ).values("id", "name", "sequence_id", "project_id", "project__identifier", "start_date", "target_date")
        }
        dependencies: t.List[t.Dict[str, t.Union[uuid.UUID, str]]] = []
        for relation_id, relation_type, issue_id, related_issue_id in relations:
            predecessor_id: uuid.UUID
            dependent_id: uuid.UUID
            predecessor_id, dependent_id = timeline_dependencies.get_dependency_direction(
                relation_type, issue_id, related_issue_id
            )
            if predecessor_id in issues and dependent_id in issues:
                dependencies.append(
                    {
                        "id": relation_id,
                        "predecessor_id": predecessor_id,
                        "dependent_id": dependent_id,
                        "relation_type": "blocking" if relation_type == "blocked_by" else relation_type,
                    }
                )
        return api_response.Response({"dependencies": dependencies, "issues": list(issues.values())})
