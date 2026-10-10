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

import plane.app.permissions as app_permissions
import plane.app.views.base as base_views
import plane.bgtasks.issue_activities_task as issue_activities_task
import plane.db.models as db_models
import plane.utils.host as host
import plane.utils.timeline_dependencies as timeline_dependencies

JsonObject: t.TypeAlias = t.Dict[str, t.Any]


def get_dependency_body(relation: db_models.IssueRelation) -> JsonObject:
    """`relation_type` reads from the predecessor: blocking, start_before or finish_before."""
    predecessor_id: uuid.UUID
    dependent_id: uuid.UUID
    predecessor_id, dependent_id = timeline_dependencies.get_dependency_direction(
        relation.relation_type, relation.issue_id, relation.related_issue_id
    )
    return {
        "id": relation.id,
        "predecessor_id": predecessor_id,
        "dependent_id": dependent_id,
        "relation_type": "blocking" if relation.relation_type == "blocked_by" else relation.relation_type,
        "delay": relation.delay,
    }


def get_issue_bodies(slug: str, issue_ids: t.List[uuid.UUID]) -> t.List[JsonObject]:
    return list(
        db_models.Issue.issue_objects.filter(workspace__slug=slug, pk__in=issue_ids).values(
            "id",
            "name",
            "sequence_id",
            "project_id",
            "project__identifier",
            "start_date",
            "target_date",
            "is_start_fixed",
        )
    )


def record_activity(
    request: api_request.Request,
    activity_type: str,
    issue_id: uuid.UUID,
    project_id: uuid.UUID,
    requested_data: JsonObject,
    current_instance: t.Optional[JsonObject],
    notification: bool,
) -> None:
    issue_activities_task.issue_activity.delay(
        type=activity_type,
        requested_data=json.dumps(requested_data, cls=django_json.DjangoJSONEncoder),
        current_instance=current_instance and json.dumps(current_instance, cls=django_json.DjangoJSONEncoder),
        issue_id=str(issue_id),
        actor_id=str(request.user.id),
        project_id=str(project_id),
        epoch=int(django_timezone.now().timestamp()),
        notification=notification,
        origin=host.base_host(request=request, is_app=True),
    )


class TimelineDependenciesEndpoint(base_views.BaseAPIView):
    permission_classes = [app_permissions.ProjectEntityPermission]

    def get(self, request: api_request.Request, slug: str, project_id: uuid.UUID) -> api_response.Response:
        """Dependencies with at least one end in the project, and the work items at their ends: the timeline
        draws a dependency even when its other work item is in another project or filtered out of the layout."""
        relations: t.List[db_models.IssueRelation] = list(
            db_models.IssueRelation.objects.filter(
                django_models.Q(issue__project_id=project_id) | django_models.Q(related_issue__project_id=project_id),
                workspace__slug=slug,
                relation_type__in=timeline_dependencies.DEPENDENCY_TYPES,
            )
        )
        issues: t.List[JsonObject] = get_issue_bodies(
            slug, [issue_id for relation in relations for issue_id in (relation.issue_id, relation.related_issue_id)]
        )
        issue_ids: t.Set[uuid.UUID] = {issue["id"] for issue in issues}
        return api_response.Response(
            {
                "dependencies": [
                    get_dependency_body(relation)
                    for relation in relations
                    if relation.issue_id in issue_ids and relation.related_issue_id in issue_ids
                ],
                "issues": issues,
            }
        )

    def post(self, request: api_request.Request, slug: str, project_id: uuid.UUID) -> api_response.Response:
        """Saves what one operation on the timeline changed, all of it or nothing: `removed_dependencies` are
        removed, each of `dependencies` is created or gets its delay, and each of `issues` gets the dates
        and the `is_start_fixed` it names. A dependency of another type between the same work items is
        changed by removing it and giving the new one. The timeline computes the dates: nothing is derived
        here, only a dependency that would create a cycle is refused. Answers as `get` does, with the given
        dependencies and work items as they are stored now."""
        serializer: timeline_dependencies.TimelineChangesSerializer = timeline_dependencies.TimelineChangesSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        changes: JsonObject = serializer.validated_data
        project: db_models.Project = db_models.Project.objects.get(pk=project_id, workspace__slug=slug)
        with django_transaction.atomic():
            removed: t.List[db_models.IssueRelation] = timeline_dependencies.remove_dependencies(
                project.workspace_id, changes["removed_dependencies"]
            )
            created: t.List[db_models.IssueRelation]
            saved: t.List[db_models.IssueRelation]
            created, saved = timeline_dependencies.save_dependencies(project, changes["dependencies"], request.user)
            changed_issues: t.List[t.Tuple[db_models.Issue, timeline_dependencies.IssueDates]] = (
                timeline_dependencies.save_issue_updates(
                    db_models.Issue.issue_objects.filter(workspace_id=project.workspace_id), changes["issues"]
                )
            )

        relation: db_models.IssueRelation
        for relation in removed:
            dependency: JsonObject = get_dependency_body(relation)
            record_activity(
                request,
                "issue_relation.activity.deleted",
                dependency["predecessor_id"],
                project_id,
                {"related_issue": dependency["dependent_id"], "relation_type": dependency["relation_type"]},
                None,
                True,
            )
        for relation in created:
            dependency = get_dependency_body(relation)
            record_activity(
                request,
                "issue_relation.activity.created",
                dependency["predecessor_id"],
                project_id,
                {"relation_type": dependency["relation_type"], "issues": [dependency["dependent_id"]]},
                None,
                True,
            )
        issue: db_models.Issue
        previous_dates: timeline_dependencies.IssueDates
        # One operation can move many work items: their dates are recorded without a notification, as
        # `issue-dates/` records them.
        for issue, previous_dates in changed_issues:
            record_activity(
                request,
                "issue.activity.updated",
                issue.id,
                issue.project_id,
                {"start_date": issue.start_date, "target_date": issue.target_date},
                dict(previous_dates),
                False,
            )
        return api_response.Response(
            {
                "dependencies": [get_dependency_body(relation) for relation in saved],
                "issues": get_issue_bodies(slug, [update["id"] for update in changes["issues"]]),
            }
        )
