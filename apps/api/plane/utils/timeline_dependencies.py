# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import collections
import datetime
import graphlib
import typing as t
import uuid

import rest_framework.serializers as api_serializers

import plane.db.models as db_models
import plane.utils.issue_relation_mapper as issue_relation_mapper

DEPENDENCY_TYPES: t.Tuple[str, ...] = ("blocked_by", "start_before", "finish_before")


class IssueDates(t.TypedDict):
    start_date: t.Optional[datetime.date]
    target_date: t.Optional[datetime.date]


class IssueDateUpdateSerializer(api_serializers.Serializer):
    id = api_serializers.UUIDField()
    start_date = api_serializers.DateField(required=False, allow_null=True)
    target_date = api_serializers.DateField(required=False, allow_null=True)


def get_dependency_direction(
    relation_type: str, issue_id: uuid.UUID, related_issue_id: uuid.UUID
) -> t.Tuple[uuid.UUID, uuid.UUID]:
    """Predecessor and dependent of a stored relation: only `blocked_by` names the dependent first."""
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


def get_date_deficit(predecessor: db_models.Issue, dependent: db_models.Issue, relation_type: str) -> int:
    """Days the dependent starts or finishes too early; a dependency constrains only work items with both dates."""
    if None in (predecessor.start_date, predecessor.target_date, dependent.start_date, dependent.target_date):
        return 0
    predecessor_date: datetime.date = (
        predecessor.start_date if relation_type == "start_before" else predecessor.target_date
    )
    dependent_date: datetime.date = dependent.target_date if relation_type == "finish_before" else dependent.start_date
    return (predecessor_date - dependent_date).days


def schedule_issue_dates(
    project: db_models.Project, updates: t.List[t.Dict[str, t.Optional[str]]]
) -> t.List[t.Tuple[db_models.Issue, IssueDates]]:
    """Set the requested dates on the project's work items and move their dependents later where a dependency
    would otherwise be violated. Returns each changed work item with its previous dates."""
    serializer: IssueDateUpdateSerializer = IssueDateUpdateSerializer(data=updates, many=True)
    serializer.is_valid(raise_exception=True)
    requested: t.Dict[uuid.UUID, t.Dict[str, t.Union[uuid.UUID, datetime.date, None]]] = {
        update["id"]: update for update in serializer.validated_data
    }
    requested_issue_ids: t.Set[uuid.UUID] = set(
        db_models.Issue.issue_objects.filter(project_id=project.id, pk__in=requested).values_list("id", flat=True)
    )

    successors: t.DefaultDict[uuid.UUID, t.List[uuid.UUID]] = collections.defaultdict(list)
    predecessors: t.DefaultDict[uuid.UUID, t.List[t.Tuple[uuid.UUID, str]]] = collections.defaultdict(list)
    predecessor_id: uuid.UUID
    dependent_id: uuid.UUID
    relation_type: str
    for predecessor_id, dependent_id, relation_type in get_dependencies(project.workspace_id):
        successors[predecessor_id].append(dependent_id)
        predecessors[dependent_id].append((predecessor_id, relation_type))
    affected: t.Set[uuid.UUID] = collect_dependents(successors, requested_issue_ids)

    issue: db_models.Issue
    issue_id: uuid.UUID
    issues: t.Dict[uuid.UUID, db_models.Issue] = {
        issue.id: issue
        for issue in db_models.Issue.issue_objects.filter(
            workspace_id=project.workspace_id,
            pk__in=affected | {predecessor_id for issue_id in affected for predecessor_id, _ in predecessors[issue_id]},
        )
    }
    previous_dates: t.Dict[uuid.UUID, IssueDates] = {
        issue.id: {"start_date": issue.start_date, "target_date": issue.target_date} for issue in issues.values()
    }

    for issue_id in requested_issue_ids:
        issue = issues[issue_id]
        issue.start_date = requested[issue_id].get("start_date", issue.start_date)
        issue.target_date = requested[issue_id].get("target_date", issue.target_date)
        if issue.start_date and issue.target_date and issue.start_date > issue.target_date:
            raise api_serializers.ValidationError({"message": "Start date cannot exceed target date"})

    try:
        dependency_order: t.List[uuid.UUID] = list(
            graphlib.TopologicalSorter(
                {
                    issue_id: [
                        predecessor_id for predecessor_id, _ in predecessors[issue_id] if predecessor_id in affected
                    ]
                    for issue_id in affected
                }
            ).static_order()
        )
    except graphlib.CycleError:
        raise api_serializers.ValidationError({"message": "The dependencies of these work items form a cycle"})
    for issue_id in dependency_order:
        if issue_id in requested_issue_ids or issue_id not in issues:
            continue
        issue = issues[issue_id]
        deficit: int = max(
            (
                get_date_deficit(issues[predecessor_id], issue, relation_type)
                for predecessor_id, relation_type in predecessors[issue_id]
                if predecessor_id in issues
            ),
            default=0,
        )
        if deficit > 0:
            issue.start_date += datetime.timedelta(days=deficit)
            issue.target_date += datetime.timedelta(days=deficit)

    changed: t.List[t.Tuple[db_models.Issue, IssueDates]] = [
        (issue, previous_dates[issue.id])
        for issue in issues.values()
        if previous_dates[issue.id] != {"start_date": issue.start_date, "target_date": issue.target_date}
    ]
    db_models.Issue.objects.bulk_update([issue for issue, _ in changed], ["start_date", "target_date"])
    return changed
