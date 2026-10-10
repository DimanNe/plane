# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import collections
import datetime
import typing as t
import uuid

import django.db.models as django_models
import rest_framework.serializers as api_serializers

import plane.db.models as db_models
import plane.utils.issue_relation_mapper as issue_relation_mapper

DEPENDENCY_TYPES: t.Tuple[str, ...] = ("blocked_by", "start_before", "finish_before")
# The same types as the timeline states them: read from the predecessor.
PREDECESSOR_RELATION_TYPES: t.Tuple[str, ...] = ("blocking", "start_before", "finish_before")


class IssueDates(t.TypedDict):
    start_date: t.Optional[datetime.date]
    target_date: t.Optional[datetime.date]


class IssueDateUpdateSerializer(api_serializers.Serializer):
    id = api_serializers.UUIDField()
    start_date = api_serializers.DateField(required=False, allow_null=True)
    target_date = api_serializers.DateField(required=False, allow_null=True)
    is_start_fixed = api_serializers.BooleanField(required=False)


class DependencySerializer(api_serializers.ModelSerializer):
    predecessor_id = api_serializers.UUIDField()
    dependent_id = api_serializers.UUIDField()
    relation_type = api_serializers.ChoiceField(choices=PREDECESSOR_RELATION_TYPES)

    class Meta:
        model = db_models.IssueRelation
        fields = ["predecessor_id", "dependent_id", "relation_type", "delay"]
        extra_kwargs = {"delay": {"required": True}}


class TimelineChangesSerializer(api_serializers.Serializer):
    dependencies = DependencySerializer(many=True)
    removed_dependencies = api_serializers.ListField(child=api_serializers.UUIDField())
    issues = IssueDateUpdateSerializer(many=True)


def get_dependency_direction(
    relation_type: str, issue_id: uuid.UUID, related_issue_id: uuid.UUID
) -> t.Tuple[uuid.UUID, uuid.UUID]:
    """Predecessor and dependent of a stored relation: only `blocked_by` names the dependent first.
    The other way round it gives the work items as the relation stores them."""
    return (related_issue_id, issue_id) if relation_type == "blocked_by" else (issue_id, related_issue_id)


def get_dependencies(workspace_id: uuid.UUID) -> t.List[t.Tuple[uuid.UUID, uuid.UUID, str]]:
    """Predecessor, dependent and relation type of every dependency in the workspace."""
    return [
        (*get_dependency_direction(relation_type, issue_id, related_issue_id), relation_type)
        for relation_type, issue_id, related_issue_id in db_models.IssueRelation.objects.filter(
            workspace_id=workspace_id, relation_type__in=DEPENDENCY_TYPES
        ).values_list("relation_type", "issue_id", "related_issue_id")
    ]


def collect_dependents(
    successors: t.Mapping[uuid.UUID, t.List[uuid.UUID]], issue_ids: t.Iterable[uuid.UUID]
) -> t.Set[uuid.UUID]:
    """The given work items and every work item that depends on them, directly or through others."""
    dependents: t.Set[uuid.UUID] = set()
    queue: t.List[uuid.UUID] = list(issue_ids)
    while queue:
        issue_id: uuid.UUID = queue.pop()
        if issue_id not in dependents:
            dependents.add(issue_id)
            queue.extend(successors.get(issue_id, []))
    return dependents


def create_issue_relations(
    project: db_models.Project,
    issue_id: uuid.UUID,
    related_issue_ids: t.Iterable[t.Union[str, uuid.UUID]],
    relation_type: str,
    actor: db_models.User,
    delay: int = 0,
) -> t.List[db_models.IssueRelation]:
    actual_relation: str = issue_relation_mapper.get_actual_relation(relation_type)
    is_reverse: bool = relation_type in ("blocking", "start_after", "finish_after")
    # Relations can cross projects, so the workspace alone scopes the related work items.
    related_issue_ids = list(
        db_models.Issue.issue_objects.filter(workspace_id=project.workspace_id, pk__in=related_issue_ids).values_list(
            "id", flat=True
        )
    )
    pairs: t.List[t.Tuple[uuid.UUID, uuid.UUID]] = [
        (related_issue_id, issue_id) if is_reverse else (issue_id, related_issue_id)
        for related_issue_id in related_issue_ids
    ]
    if actual_relation in DEPENDENCY_TYPES:
        successors: t.DefaultDict[uuid.UUID, t.List[uuid.UUID]] = collections.defaultdict(list)
        relation_types: t.Dict[t.Tuple[uuid.UUID, uuid.UUID], str] = {}
        predecessor_id: uuid.UUID
        dependent_id: uuid.UUID
        existing_relation: str
        for predecessor_id, dependent_id, existing_relation in get_dependencies(project.workspace_id):
            successors[predecessor_id].append(dependent_id)
            relation_types[(predecessor_id, dependent_id)] = existing_relation
        pair: t.Tuple[uuid.UUID, uuid.UUID]
        for pair in pairs:
            predecessor_id, dependent_id = get_dependency_direction(actual_relation, *pair)
            # `blocked_by` is stored from the dependent and the other types from the predecessor. Unchecked, a second
            # type between two work items is therefore saved as a second relation or dropped without an error.
            if relation_types.get((predecessor_id, dependent_id), actual_relation) != actual_relation:
                raise api_serializers.ValidationError({"error": "These work items already have a dependency"})
            if predecessor_id in collect_dependents(successors, [dependent_id]):
                raise api_serializers.ValidationError({"error": "This dependency would create a cycle"})
            successors[predecessor_id].append(dependent_id)
    return db_models.IssueRelation.objects.bulk_create(
        [
            db_models.IssueRelation(
                issue_id=pair[0],
                related_issue_id=pair[1],
                relation_type=actual_relation,
                delay=delay,
                project_id=project.id,
                workspace_id=project.workspace_id,
                created_by=actor,
                updated_by=actor,
            )
            for pair in pairs
        ],
        batch_size=10,
        ignore_conflicts=True,
    )


def save_issue_updates(
    issues: django_models.QuerySet[db_models.Issue], updates: t.List[t.Dict[str, t.Any]]
) -> t.List[t.Tuple[db_models.Issue, IssueDates]]:
    """Set the requested dates, and whether the start is fixed, on those of the given work items that the
    updates name. Nothing is derived from dependencies: the timeline computes the dates it saves.
    Returns each changed work item with its previous dates."""
    requested: t.Dict[uuid.UUID, t.Dict[str, t.Any]] = {update["id"]: update for update in updates}
    changed: t.List[t.Tuple[db_models.Issue, IssueDates]] = []
    issue: db_models.Issue
    for issue in issues.filter(pk__in=requested):
        previous_dates: IssueDates = {"start_date": issue.start_date, "target_date": issue.target_date}
        was_start_fixed: bool = issue.is_start_fixed
        field: str
        for field in ("start_date", "target_date", "is_start_fixed"):
            setattr(issue, field, requested[issue.id].get(field, getattr(issue, field)))
        if issue.start_date and issue.target_date and issue.start_date > issue.target_date:
            raise api_serializers.ValidationError({"message": "Start date cannot exceed target date"})
        if (previous_dates, was_start_fixed) != (
            {"start_date": issue.start_date, "target_date": issue.target_date},
            issue.is_start_fixed,
        ):
            changed.append((issue, previous_dates))
    db_models.Issue.objects.bulk_update(
        [issue for issue, _ in changed], ["start_date", "target_date", "is_start_fixed"]
    )
    return changed


def set_issue_dates(
    project: db_models.Project, updates: t.List[t.Dict[str, t.Optional[str]]]
) -> t.List[t.Tuple[db_models.Issue, IssueDates]]:
    """Set the requested dates on the project's work items. Returns each changed work item with its
    previous dates."""
    serializer: IssueDateUpdateSerializer = IssueDateUpdateSerializer(data=updates, many=True)
    serializer.is_valid(raise_exception=True)
    return save_issue_updates(db_models.Issue.issue_objects.filter(project_id=project.id), serializer.validated_data)


def remove_dependencies(workspace_id: uuid.UUID, relation_ids: t.List[uuid.UUID]) -> t.List[db_models.IssueRelation]:
    """Remove those of the given relations that are dependencies of the workspace, and return them."""
    removed: t.List[db_models.IssueRelation] = list(
        db_models.IssueRelation.objects.filter(
            workspace_id=workspace_id, pk__in=relation_ids, relation_type__in=DEPENDENCY_TYPES
        )
    )
    relation: db_models.IssueRelation
    for relation in removed:
        relation.delete()
    return removed


def save_dependencies(
    project: db_models.Project, dependencies: t.List[t.Dict[str, t.Any]], actor: db_models.User
) -> t.Tuple[t.List[db_models.IssueRelation], t.List[db_models.IssueRelation]]:
    """Create each given dependency or, where one of its type exists between its work items, set its delay.
    Returns the created ones and all of them."""
    created: t.List[db_models.IssueRelation] = []
    saved: t.List[db_models.IssueRelation] = []
    dependency: t.Dict[str, t.Any]
    for dependency in dependencies:
        actual_relation: str = issue_relation_mapper.get_actual_relation(dependency["relation_type"])
        issue_id: uuid.UUID
        related_issue_id: uuid.UUID
        issue_id, related_issue_id = get_dependency_direction(
            actual_relation, dependency["predecessor_id"], dependency["dependent_id"]
        )
        stored: django_models.QuerySet[db_models.IssueRelation] = db_models.IssueRelation.objects.filter(
            workspace_id=project.workspace_id,
            issue_id=issue_id,
            related_issue_id=related_issue_id,
            relation_type=actual_relation,
        )
        relation: t.Optional[db_models.IssueRelation] = stored.first()
        if relation is None:
            ends: t.Set[uuid.UUID] = {issue_id, related_issue_id}
            if db_models.Issue.issue_objects.filter(workspace_id=project.workspace_id, pk__in=ends).count() != 2:
                raise api_serializers.ValidationError(
                    {"error": "A dependency needs two work items of the workspace that are not archived"}
                )
            create_issue_relations(
                project,
                dependency["predecessor_id"],
                [dependency["dependent_id"]],
                dependency["relation_type"],
                actor,
                dependency["delay"],
            )
            relation = stored.first()
            # A relation of another kind that is stored between the same work items in the same order keeps
            # the dependency from being stored, without an error.
            if relation is None:
                raise api_serializers.ValidationError(
                    {"error": "These work items already have a relation in this direction"}
                )
            created.append(relation)
        elif relation.delay != dependency["delay"]:
            relation.delay = dependency["delay"]
            relation.save()
        saved.append(relation)
    return created, saved
