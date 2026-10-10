# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import datetime
import json
import typing as t
import unittest.mock as mock
import uuid

import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.bgtasks.issue_activities_task as issue_activities_task
import plane.bgtasks.notification_task as notification_task
import plane.db.models as db_models

pytestmark = [pytest.mark.django_db, pytest.mark.contract]

JsonObject: t.TypeAlias = t.Dict[str, t.Any]


@pytest.fixture(name="project")
def create_project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(name="Timeline", identifier="TL", workspace=workspace)
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=20)
    return project


@pytest.fixture(name="other_project")
def create_other_project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(name="Other", identifier="OTH", workspace=workspace)
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=20)
    return project


@pytest.fixture(name="inline_issue_activity")
def run_issue_activity_inline() -> t.Iterator[None]:
    """No worker consumes the queue in tests, so the activity task runs inside the request."""
    with mock.patch.object(
        issue_activities_task.issue_activity, "delay", side_effect=issue_activities_task.issue_activity.run
    ):
        yield


def get_url(project: db_models.Project, path: str) -> str:
    return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/{path}"


def create_issue(project: db_models.Project, name: str, dates: str = "None..None", **fields: t.Any) -> db_models.Issue:
    """`dates` is `start..target`, each an ISO date or None, as `get_issue_dates` reports them."""
    start_date: str
    target_date: str
    start_date, target_date = dates.split("..")
    return db_models.Issue.objects.create(
        project=project,
        name=name,
        start_date=None if start_date == "None" else start_date,
        target_date=None if target_date == "None" else target_date,
        **fields,
    )


def get_issue_dates() -> t.Dict[str, str]:
    return {
        name: f"{start_date}..{target_date}"
        for name, start_date, target_date in db_models.Issue.objects.values_list("name", "start_date", "target_date")
    }


def get_relations() -> t.Set[t.Tuple[str, uuid.UUID, uuid.UUID]]:
    return set(db_models.IssueRelation.objects.values_list("relation_type", "issue_id", "related_issue_id"))


def create_relation(
    issue: db_models.Issue, relation_type: str, related_issue: db_models.Issue, delay: int = 0
) -> db_models.IssueRelation:
    return db_models.IssueRelation.objects.create(
        project=issue.project, issue=issue, relation_type=relation_type, related_issue=related_issue, delay=delay
    )


def get_activities() -> t.Set[t.Tuple[str, str, t.Optional[str], t.Optional[str]]]:
    """Work item name, field, old and new value of every recorded activity."""
    return set(db_models.IssueActivity.objects.values_list("issue__name", "field", "old_value", "new_value"))


def format_timestamp(value: datetime.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def get_milestone_body(milestone: db_models.Milestone, **fields: t.Any) -> JsonObject:
    """Response body of a milestone: generated values come from the row, the others are stated by the test."""
    return {
        "id": str(milestone.id),
        "title": milestone.title,
        "description_html": "<p></p>",
        "target_date": None,
        "external_source": None,
        "external_id": None,
        "total_issues": 0,
        "completed_issues": 0,
        "cancelled_issues": 0,
        "project": str(milestone.project_id),
        "workspace": str(milestone.workspace_id),
        "created_by": milestone.created_by_id and str(milestone.created_by_id),
        "updated_by": milestone.updated_by_id and str(milestone.updated_by_id),
        "created_at": format_timestamp(milestone.created_at),
        "updated_at": format_timestamp(milestone.updated_at),
        "deleted_at": None,
        **fields,
    }


def sort_by_id(rows: t.List[JsonObject]) -> t.List[JsonObject]:
    return sorted(rows, key=lambda row: row["id"])


@pytest.mark.parametrize(
    "relation_type, is_reverse, stored_relation_type",
    [
        pytest.param("blocked_by", False, "blocked_by", id="blocked_by"),
        pytest.param("blocking", True, "blocked_by", id="blocking"),
        pytest.param("start_before", False, "start_before", id="start_before"),
        pytest.param("start_after", True, "start_before", id="start_after"),
        pytest.param("finish_before", False, "finish_before", id="finish_before"),
        pytest.param("finish_after", True, "finish_before", id="finish_after"),
    ],
)
def test_create_relation_stores_each_dependency_in_one_direction(
    project: db_models.Project,
    session_client: api_test.APIClient,
    relation_type: str,
    is_reverse: bool,
    stored_relation_type: str,
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")

    response: api_response.Response = session_client.post(
        get_url(project, f"issues/{a.id}/issue-relation/"),
        {"relation_type": relation_type, "issues": [str(b.id)]},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert get_relations() == {(stored_relation_type, b.id, a.id) if is_reverse else (stored_relation_type, a.id, b.id)}


def test_create_relation_twice_keeps_one_relation(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    url: str = get_url(project, f"issues/{a.id}/issue-relation/")
    body: JsonObject = {"relation_type": "blocking", "issues": [str(b.id)]}
    session_client.post(url, body, format="json")

    response: api_response.Response = session_client.post(url, body, format="json")

    assert response.status_code == 201, response.content
    assert get_relations() == {("blocked_by", b.id, a.id)}


@pytest.mark.parametrize(
    "issue_name, relation_type, related_issue_name",
    [
        pytest.param("A", "start_before", "B", id="stored-in-the-other-order"),
        pytest.param("B", "finish_after", "A", id="stated-from-the-dependent"),
        pytest.param("C", "finish_after", "B", id="stored-in-the-same-order"),
    ],
)
def test_create_dependency_of_another_type_between_the_same_work_items_is_rejected(
    project: db_models.Project,
    session_client: api_test.APIClient,
    issue_name: str,
    relation_type: str,
    related_issue_name: str,
) -> None:
    issues: t.Dict[str, db_models.Issue] = {name: create_issue(project, name) for name in "ABC"}
    create_relation(issues["B"], "blocked_by", issues["A"])
    create_relation(issues["B"], "start_before", issues["C"])
    relations: t.Set[t.Tuple[str, uuid.UUID, uuid.UUID]] = get_relations()

    response: api_response.Response = session_client.post(
        get_url(project, f"issues/{issues[issue_name].id}/issue-relation/"),
        {"relation_type": relation_type, "issues": [str(issues[related_issue_name].id)]},
        format="json",
    )

    assert (response.status_code, response.json()) == (400, {"error": "These work items already have a dependency"})
    assert get_relations() == relations


@pytest.mark.parametrize(
    "issue_name, relation_type, related_issue_name",
    [
        pytest.param("C", "finish_before", "A", id="through-other-dependency-types"),
        pytest.param("A", "blocked_by", "C", id="stated-from-the-dependent"),
        pytest.param("B", "blocking", "A", id="opposite-of-existing-dependency"),
        pytest.param("A", "start_before", "A", id="on-itself"),
    ],
)
def test_create_dependency_that_closes_a_cycle_is_rejected(
    project: db_models.Project,
    session_client: api_test.APIClient,
    issue_name: str,
    relation_type: str,
    related_issue_name: str,
) -> None:
    issues: t.Dict[str, db_models.Issue] = {name: create_issue(project, name) for name in "ABC"}
    create_relation(issues["B"], "blocked_by", issues["A"])
    create_relation(issues["B"], "start_before", issues["C"])
    relations: t.Set[t.Tuple[str, uuid.UUID, uuid.UUID]] = get_relations()

    response: api_response.Response = session_client.post(
        get_url(project, f"issues/{issues[issue_name].id}/issue-relation/"),
        {"relation_type": relation_type, "issues": [str(issues[related_issue_name].id)]},
        format="json",
    )

    assert (response.status_code, response.json()) == (400, {"error": "This dependency would create a cycle"})
    assert get_relations() == relations


def test_create_relation_other_than_dependency_is_not_checked_for_cycles(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    create_relation(b, "blocked_by", a)

    response: api_response.Response = session_client.post(
        get_url(project, f"issues/{a.id}/issue-relation/"),
        {"relation_type": "implemented_by", "issues": [str(b.id)]},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert get_relations() == {("blocked_by", b.id, a.id), ("implemented_by", a.id, b.id)}


def test_remove_relation_between_unrelated_work_items_succeeds(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")

    response: api_response.Response = session_client.post(
        get_url(project, f"issues/{a.id}/remove-relation/"), {"related_issue": str(b.id)}, format="json"
    )

    assert response.status_code == 204, response.content


def test_remove_relation_removes_the_relation_of_the_given_type(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    create_relation(b, "blocked_by", a)
    create_relation(a, "relates_to", b)

    response: api_response.Response = session_client.post(
        get_url(project, f"issues/{a.id}/remove-relation/"),
        {"related_issue": str(b.id), "relation_type": "blocking"},
        format="json",
    )

    assert response.status_code == 204, response.content
    assert get_relations() == {("relates_to", a.id, b.id)}


def test_timeline_dependencies_lists_dependencies_touching_the_project(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A", "2026-01-01..2026-01-03")
    b: db_models.Issue = create_issue(project, "B", is_start_fixed=False)
    c: db_models.Issue = create_issue(other_project, "C")
    d: db_models.Issue = create_issue(other_project, "D")
    blocked_by: db_models.IssueRelation = create_relation(b, "blocked_by", a, delay=2)
    start_before: db_models.IssueRelation = create_relation(b, "start_before", c)
    create_relation(c, "finish_before", d)
    create_relation(a, "relates_to", d)

    response: api_response.Response = session_client.get(get_url(project, "timeline-dependencies/"))

    assert response.status_code == 200, response.content
    actual: JsonObject = response.json()
    assert {key: sort_by_id(rows) for key, rows in actual.items()} == {
        "dependencies": sort_by_id(
            [
                {
                    "id": str(blocked_by.id),
                    "predecessor_id": str(a.id),
                    "dependent_id": str(b.id),
                    "relation_type": "blocking",
                    "delay": 2,
                },
                {
                    "id": str(start_before.id),
                    "predecessor_id": str(b.id),
                    "dependent_id": str(c.id),
                    "relation_type": "start_before",
                    "delay": 0,
                },
            ]
        ),
        "issues": sort_by_id(
            [
                {
                    "id": str(a.id),
                    "name": "A",
                    "sequence_id": a.sequence_id,
                    "project_id": str(project.id),
                    "project__identifier": "TL",
                    "start_date": "2026-01-01",
                    "target_date": "2026-01-03",
                    "is_start_fixed": True,
                },
                {
                    "id": str(b.id),
                    "name": "B",
                    "sequence_id": b.sequence_id,
                    "project_id": str(project.id),
                    "project__identifier": "TL",
                    "start_date": None,
                    "target_date": None,
                    "is_start_fixed": False,
                },
                {
                    "id": str(c.id),
                    "name": "C",
                    "sequence_id": c.sequence_id,
                    "project_id": str(other_project.id),
                    "project__identifier": "OTH",
                    "start_date": None,
                    "target_date": None,
                    "is_start_fixed": True,
                },
            ]
        ),
    }


def create_issues_and_relations(
    project: db_models.Project,
    other_project: db_models.Project,
    dates: t.Dict[str, str],
    relations: t.Sequence[t.Tuple[t.Any, ...]],
) -> t.Dict[str, db_models.Issue]:
    """Create the named work items (in the other project or archived when the name says so) and their relations:
    work item, relation type, related work item and, when it is not 0, the delay."""
    issues: t.Dict[str, db_models.Issue] = {
        name: create_issue(
            other_project if name.startswith("Other") else project,
            name,
            dates[name],
            archived_at=datetime.date(2026, 1, 1) if name.startswith("Archived") else None,
        )
        for name in dates
    }
    issue_name: str
    relation_type: str
    related_issue_name: str
    delay: t.List[int]
    for issue_name, relation_type, related_issue_name, *delay in relations:
        create_relation(issues[issue_name], relation_type, issues[related_issue_name], *delay)
    return issues


def get_stored_relations() -> t.Set[t.Tuple[str, str, str, int]]:
    """Relation type, names of the work item and the related work item, and delay of every relation, as stored."""
    return set(
        db_models.IssueRelation.objects.values_list("relation_type", "issue__name", "related_issue__name", "delay")
    )


def get_issue_starts() -> t.Dict[str, t.Tuple[str, bool]]:
    """Dates of every work item as `get_issue_dates` reports them, and whether its start is fixed."""
    return {
        name: (f"{start_date}..{target_date}", is_start_fixed)
        for name, start_date, target_date, is_start_fixed in db_models.Issue.objects.values_list(
            "name", "start_date", "target_date", "is_start_fixed"
        )
    }


def post_timeline_changes(
    client: api_test.APIClient,
    project: db_models.Project,
    issues: t.Dict[str, db_models.Issue],
    dependencies: t.List[t.Tuple[str, str, str, int]],
    removed: t.List[t.Tuple[str, str]],
    updates: t.Dict[str, JsonObject],
) -> api_response.Response:
    """Post to the project: dependencies as predecessor, relation type read from it, dependent and delay; the
    stored relations to remove as work item and related work item; and the updates of the named work items."""
    return client.post(
        get_url(project, "timeline-dependencies/"),
        {
            "dependencies": [
                {
                    "predecessor_id": str(issues[predecessor_name].id),
                    "dependent_id": str(issues[dependent_name].id),
                    "relation_type": relation_type,
                    "delay": delay,
                }
                for predecessor_name, relation_type, dependent_name, delay in dependencies
            ],
            "removed_dependencies": [
                str(db_models.IssueRelation.objects.get(issue=issues[name], related_issue=issues[related_name]).id)
                for name, related_name in removed
            ],
            "issues": [{"id": str(issues[name].id), **updates[name]} for name in updates],
        },
        format="json",
    )


@pytest.mark.parametrize(
    "relations, dependencies, removed, expected_relations",
    [
        pytest.param(
            [],
            [("A", "blocking", "B", 2)],
            [],
            {("blocked_by", "B", "A", 2)},
            id="new-dependency-is-stored-with-its-delay",
        ),
        pytest.param(
            [],
            [("A", "start_before", "B", 0), ("A", "finish_before", "C", 1)],
            [],
            {("start_before", "A", "B", 0), ("finish_before", "A", "C", 1)},
            id="types-other-than-blocking-are-stored-from-the-predecessor",
        ),
        pytest.param(
            [("B", "blocked_by", "A", 1), ("A", "start_before", "C", 1)],
            [("A", "blocking", "B", 3)],
            [],
            {("blocked_by", "B", "A", 3), ("start_before", "A", "C", 1)},
            id="existing-dependency-gets-the-given-delay",
        ),
        pytest.param(
            [("B", "blocked_by", "A"), ("C", "blocked_by", "A")],
            [],
            [("B", "A")],
            {("blocked_by", "C", "A", 0)},
            id="removed-dependency-is-removed",
        ),
        pytest.param(
            [("B", "blocked_by", "A", 1)],
            [("A", "start_before", "B", 1)],
            [("B", "A")],
            {("start_before", "A", "B", 1)},
            id="type-changes-by-removing-the-dependency-and-giving-the-new-one",
        ),
        pytest.param(
            [("A", "relates_to", "B")],
            [],
            [("A", "B")],
            {("relates_to", "A", "B", 0)},
            id="relation-that-is-not-a-dependency-is-not-removed",
        ),
    ],
)
def test_save_timeline_changes_saves_the_given_dependencies(
    project: db_models.Project,
    other_project: db_models.Project,
    session_client: api_test.APIClient,
    relations: t.List[t.Tuple[t.Any, ...]],
    dependencies: t.List[t.Tuple[str, str, str, int]],
    removed: t.List[t.Tuple[str, str]],
    expected_relations: t.Set[t.Tuple[str, str, str, int]],
) -> None:
    issues: t.Dict[str, db_models.Issue] = create_issues_and_relations(
        project, other_project, {name: "None..None" for name in "ABC"}, relations
    )

    response: api_response.Response = post_timeline_changes(session_client, project, issues, dependencies, removed, {})

    assert response.status_code == 200, response.content
    assert get_stored_relations() == expected_relations


@pytest.mark.parametrize(
    "dates, relations, updates, expected_starts",
    [
        pytest.param(
            {"A": "2026-01-01..2026-01-03", "B": "2026-01-03..2026-01-05"},
            [("B", "blocked_by", "A")],
            {"A": {"start_date": "2026-01-06", "target_date": "2026-01-08", "is_start_fixed": True}},
            {"A": ("2026-01-06..2026-01-08", True), "B": ("2026-01-03..2026-01-05", True)},
            id="dependent-that-is-not-given-stays",
        ),
        pytest.param(
            {"A": "2026-01-01..2026-01-03", "Other B": "2026-01-03..2026-01-05"},
            [("Other B", "blocked_by", "A")],
            {"Other B": {"start_date": "2026-01-04", "target_date": "2026-01-06", "is_start_fixed": False}},
            {"A": ("2026-01-01..2026-01-03", True), "Other B": ("2026-01-04..2026-01-06", False)},
            id="work-item-of-another-project-is-saved",
        ),
        pytest.param(
            {"A": "2026-01-01..2026-01-03"},
            [],
            {"A": {"is_start_fixed": False}},
            {"A": ("2026-01-01..2026-01-03", False)},
            id="field-left-out-stays",
        ),
        pytest.param(
            {"Archived A": "2026-01-01..2026-01-03"},
            [],
            {"Archived A": {"start_date": "2026-01-02", "is_start_fixed": False}},
            {"Archived A": ("2026-01-01..2026-01-03", True)},
            id="archived-work-item-is-skipped",
        ),
    ],
)
def test_save_timeline_changes_sets_what_is_given_on_the_given_work_items(
    project: db_models.Project,
    other_project: db_models.Project,
    session_client: api_test.APIClient,
    dates: t.Dict[str, str],
    relations: t.List[t.Tuple[t.Any, ...]],
    updates: t.Dict[str, JsonObject],
    expected_starts: t.Dict[str, t.Tuple[str, bool]],
) -> None:
    issues: t.Dict[str, db_models.Issue] = create_issues_and_relations(project, other_project, dates, relations)

    response: api_response.Response = post_timeline_changes(session_client, project, issues, [], [], updates)

    assert response.status_code == 200, response.content
    assert get_issue_starts() == expected_starts


@pytest.mark.parametrize(
    "dependencies, updates, expected_error",
    [
        pytest.param(
            [("B", "blocking", "A", 0)],
            {"C": {"start_date": "2026-01-02"}},
            {"error": "This dependency would create a cycle"},
            id="dependency-that-closes-a-cycle",
        ),
        pytest.param(
            [("A", "finish_before", "B", 0)],
            {"C": {"start_date": "2026-01-02"}},
            {"error": "These work items already have a dependency"},
            id="another-type-between-work-items-whose-dependency-is-not-removed",
        ),
        pytest.param(
            [("B", "blocking", "Archived D", 0)],
            {"C": {"start_date": "2026-01-02"}},
            {"error": "A dependency needs two work items of the workspace that are not archived"},
            id="dependency-to-an-archived-work-item",
        ),
        pytest.param(
            [("Archived D", "blocking", "B", 0)],
            {"C": {"start_date": "2026-01-02"}},
            {"error": "A dependency needs two work items of the workspace that are not archived"},
            id="dependency-from-an-archived-work-item",
        ),
        pytest.param(
            [("A", "start_before", "E", 0)],
            {"C": {"start_date": "2026-01-02"}},
            {"error": "These work items already have a relation in this direction"},
            id="dependency-beside-another-relation-stored-in-the-same-order",
        ),
        pytest.param(
            [("B", "blocking", "E", 0)],
            {"C": {"start_date": "2026-01-02"}, "B": {"start_date": "2026-01-04"}},
            {"message": "Start date cannot exceed target date"},
            id="start-date-after-target-date",
        ),
    ],
)
def test_save_timeline_changes_that_are_refused_change_nothing(
    project: db_models.Project,
    other_project: db_models.Project,
    session_client: api_test.APIClient,
    dependencies: t.List[t.Tuple[str, str, str, int]],
    updates: t.Dict[str, JsonObject],
    expected_error: JsonObject,
) -> None:
    issues: t.Dict[str, db_models.Issue] = create_issues_and_relations(
        project,
        other_project,
        {name: "2026-01-01..2026-01-03" for name in ("A", "B", "C", "Archived D", "E")},
        [("B", "blocked_by", "A"), ("C", "blocked_by", "A"), ("A", "relates_to", "E")],
    )
    relations: t.Set[t.Tuple[str, str, str, int]] = get_stored_relations()

    response: api_response.Response = post_timeline_changes(
        session_client, project, issues, dependencies, [("C", "A")], updates
    )

    assert (response.status_code, response.json()) == (400, expected_error)
    assert (get_stored_relations(), get_issue_dates()) == (
        relations,
        {name: "2026-01-01..2026-01-03" for name in issues},
    )


def test_save_timeline_changes_answers_with_the_given_dependencies_and_work_items_as_stored(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    issues: t.Dict[str, db_models.Issue] = create_issues_and_relations(
        project,
        other_project,
        {"A": "2026-01-01..2026-01-03", "B": "2026-01-01..2026-01-02", "C": "2026-01-01..2026-01-02"},
        [("C", "blocked_by", "A"), ("A", "start_before", "B")],
    )

    response: api_response.Response = post_timeline_changes(
        session_client,
        project,
        issues,
        [("A", "blocking", "B", 1), ("A", "blocking", "C", 2)],
        [("A", "B")],
        {"B": {"start_date": "2026-01-05", "target_date": "2026-01-06", "is_start_fixed": False}},
    )

    assert (response.status_code, response.json()) == (
        200,
        {
            "dependencies": [
                {
                    "id": str(db_models.IssueRelation.objects.get(issue=issues[name], related_issue=issues["A"]).id),
                    "predecessor_id": str(issues["A"].id),
                    "dependent_id": str(issues[name].id),
                    "relation_type": "blocking",
                    "delay": delay,
                }
                for name, delay in (("B", 1), ("C", 2))
            ],
            "issues": [
                {
                    "id": str(issues["B"].id),
                    "name": "B",
                    "sequence_id": issues["B"].sequence_id,
                    "project_id": str(project.id),
                    "project__identifier": "TL",
                    "start_date": "2026-01-05",
                    "target_date": "2026-01-06",
                    "is_start_fixed": False,
                }
            ],
        },
    )


@pytest.mark.usefixtures("inline_issue_activity")
def test_save_timeline_changes_records_activity_of_dependencies_and_dates(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    issues: t.Dict[str, db_models.Issue] = create_issues_and_relations(
        project,
        other_project,
        {"A": "2026-01-01..2026-01-03", "B": "2026-01-01..2026-01-02", "C": "2026-01-01..2026-01-02"},
        [("C", "blocked_by", "A")],
    )

    post_timeline_changes(
        session_client,
        project,
        issues,
        [("A", "start_before", "B", 1)],
        [("C", "A")],
        {"B": {"start_date": "2026-01-02", "target_date": "2026-01-03", "is_start_fixed": False}},
    )

    assert get_activities() == {
        ("A", "blocking", "TL-3", ""),
        ("C", "blocked_by", "TL-1", ""),
        ("A", "start_before", "", "TL-2"),
        ("B", "start_after", "", "TL-1"),
        ("B", "start_date", "2026-01-01", "2026-01-02"),
        ("B", "target_date", "2026-01-02", "2026-01-03"),
    }


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"dependencies": [], "issues": []}, id="list-left-out"),
        pytest.param(
            {
                "dependencies": [
                    {"predecessor_id": "{A}", "dependent_id": "{B}", "relation_type": "blocked_by", "delay": 0}
                ],
                "removed_dependencies": [],
                "issues": [],
            },
            id="relation-type-not-read-from-the-predecessor",
        ),
        pytest.param(
            {
                "dependencies": [
                    {"predecessor_id": "{A}", "dependent_id": "{B}", "relation_type": "blocking", "delay": -1}
                ],
                "removed_dependencies": [],
                "issues": [],
            },
            id="negative-delay",
        ),
        pytest.param(
            {
                "dependencies": [{"predecessor_id": "{A}", "dependent_id": "{B}", "relation_type": "blocking"}],
                "removed_dependencies": [],
                "issues": [],
            },
            id="dependency-without-delay",
        ),
        pytest.param(
            {"dependencies": [], "removed_dependencies": [], "issues": [{"id": "{A}", "start_date": "tomorrow"}]},
            id="invalid-date",
        ),
    ],
)
def test_save_timeline_changes_that_are_malformed_are_rejected(
    project: db_models.Project, session_client: api_test.APIClient, changes: JsonObject
) -> None:
    a: db_models.Issue = create_issue(project, "A", "2026-01-01..2026-01-03")
    b: db_models.Issue = create_issue(project, "B")

    response: api_response.Response = session_client.post(
        get_url(project, "timeline-dependencies/"),
        json.loads(json.dumps(changes).replace("{A}", str(a.id)).replace("{B}", str(b.id))),
        format="json",
    )

    assert response.status_code == 400, response.content
    assert (get_stored_relations(), get_issue_dates()) == (set(), {"A": "2026-01-01..2026-01-03", "B": "None..None"})


def test_save_timeline_changes_neither_saves_nor_shows_a_work_item_of_another_workspace(
    project: db_models.Project, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    other_workspace: db_models.Workspace = db_models.Workspace.objects.create(
        name="Other", owner=create_user, slug="other-workspace"
    )
    a: db_models.Issue = create_issue(
        db_models.Project.objects.create(name="Elsewhere", identifier="ELS", workspace=other_workspace),
        "A",
        "2026-01-01..2026-01-03",
    )

    response: api_response.Response = session_client.post(
        get_url(project, "timeline-dependencies/"),
        {"dependencies": [], "removed_dependencies": [], "issues": [{"id": str(a.id), "start_date": "2026-01-02"}]},
        format="json",
    )

    assert (response.status_code, response.json()) == (200, {"dependencies": [], "issues": []})
    assert get_issue_dates() == {"A": "2026-01-01..2026-01-03"}


def test_save_timeline_changes_is_refused_to_a_guest_of_the_project(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A", "2026-01-01..2026-01-03")
    db_models.ProjectMember.objects.filter(project=project).update(role=5)

    response: api_response.Response = session_client.post(
        get_url(project, "timeline-dependencies/"),
        {"dependencies": [], "removed_dependencies": [], "issues": [{"id": str(a.id), "start_date": "2026-01-02"}]},
        format="json",
    )

    assert response.status_code == 403, response.content
    assert get_issue_dates() == {"A": "2026-01-01..2026-01-03"}


def post_issue_dates(
    client: api_test.APIClient,
    project: db_models.Project,
    other_project: db_models.Project,
    dates: t.Dict[str, str],
    relations: t.List[t.Tuple[str, str, str]],
    updates: t.Dict[str, JsonObject],
) -> api_response.Response:
    """Create the work items and relations, then post the updates of the named work items to the project."""
    issues: t.Dict[str, db_models.Issue] = create_issues_and_relations(project, other_project, dates, relations)
    return client.post(
        get_url(project, "issue-dates/"),
        {"updates": [{"id": str(issues[name].id), **updates[name]} for name in updates]},
        format="json",
    )


@pytest.mark.parametrize(
    "dates, relations, updates, expected_dates",
    [
        pytest.param(
            {"A": "2026-01-01..2026-01-03", "B": "2026-01-03..2026-01-05", "C": "2026-01-05..2026-01-08"},
            [("B", "blocked_by", "A"), ("A", "start_before", "C")],
            {"A": {"start_date": "2026-01-06", "target_date": "2026-01-08"}},
            {"A": "2026-01-06..2026-01-08", "B": "2026-01-03..2026-01-05", "C": "2026-01-05..2026-01-08"},
            id="dependents-of-a-moved-work-item-stay",
        ),
        pytest.param(
            {"A": "2026-01-01..2026-01-03"},
            [],
            {"A": {"target_date": None}},
            {"A": "2026-01-01..None"},
            id="null-clears-a-date-and-a-date-left-out-stays",
        ),
        pytest.param(
            {"Other A": "2026-01-01..2026-01-03"},
            [],
            {"Other A": {"target_date": "2026-01-09"}},
            {"Other A": "2026-01-01..2026-01-03"},
            id="work-item-of-another-project-is-skipped",
        ),
    ],
)
def test_issue_dates_set_only_the_requested_dates(
    project: db_models.Project,
    other_project: db_models.Project,
    session_client: api_test.APIClient,
    dates: t.Dict[str, str],
    relations: t.List[t.Tuple[str, str, str]],
    updates: t.Dict[str, JsonObject],
    expected_dates: t.Dict[str, str],
) -> None:
    response: api_response.Response = post_issue_dates(
        session_client, project, other_project, dates, relations, updates
    )

    assert response.status_code == 200, response.content
    assert get_issue_dates() == expected_dates


def test_issue_dates_with_a_start_after_the_target_change_nothing(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    dates: t.Dict[str, str] = {"A": "2026-01-01..2026-01-03", "B": "2026-01-01..2026-01-03"}

    response: api_response.Response = post_issue_dates(
        session_client,
        project,
        other_project,
        dates,
        [],
        {"A": {"target_date": "2026-02-01"}, "B": {"start_date": "2026-01-04"}},
    )

    assert (response.status_code, response.json()) == (400, {"message": "Start date cannot exceed target date"})
    assert get_issue_dates() == dates


@pytest.mark.parametrize(
    "updates",
    [
        pytest.param({"id": "{A}", "target_date": "2026-01-09"}, id="updates-not-a-list"),
        pytest.param([{"id": "{A}", "target_date": "tomorrow"}], id="invalid-date"),
        pytest.param([{"target_date": "2026-01-09"}], id="update-without-id"),
    ],
)
def test_issue_dates_with_malformed_updates_are_rejected(
    project: db_models.Project,
    session_client: api_test.APIClient,
    updates: t.Union[JsonObject, t.List[JsonObject]],
) -> None:
    a: db_models.Issue = create_issue(project, "A", "2026-01-01..2026-01-03")

    response: api_response.Response = session_client.post(
        get_url(project, "issue-dates/"),
        {"updates": json.loads(json.dumps(updates).replace("{A}", str(a.id)))},
        format="json",
    )

    assert response.status_code == 400, response.content
    assert get_issue_dates() == {"A": "2026-01-01..2026-01-03"}


def test_issue_dates_return_the_changed_work_items(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A", "2026-01-01..2026-01-03")
    b: db_models.Issue = create_issue(project, "B", "2026-01-03..2026-01-05")

    response: api_response.Response = session_client.post(
        get_url(project, "issue-dates/"),
        {"updates": [{"id": str(a.id), "target_date": "2026-01-04"}, {"id": str(b.id), "target_date": "2026-01-05"}]},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        200,
        {"updates": [{"id": str(a.id), "start_date": "2026-01-01", "target_date": "2026-01-04"}]},
    )


@pytest.mark.usefixtures("inline_issue_activity")
def test_issue_dates_record_activity_on_every_changed_work_item(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A", "2026-01-01..2026-01-03")
    b: db_models.Issue = create_issue(project, "B", "2026-01-03..2026-01-05")

    session_client.post(
        get_url(project, "issue-dates/"),
        {
            "updates": [
                {"id": str(a.id), "target_date": "2026-01-04"},
                {"id": str(b.id), "start_date": "2026-01-04", "target_date": "2026-01-06"},
            ]
        },
        format="json",
    )

    assert get_activities() == {
        ("A", "target_date", "2026-01-03", "2026-01-04"),
        ("B", "start_date", "2026-01-03", "2026-01-04"),
        ("B", "target_date", "2026-01-05", "2026-01-06"),
    }


def test_create_milestone(
    project: db_models.Project, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    response: api_response.Response = session_client.post(
        get_url(project, "milestones/"),
        {"title": "Beta", "target_date": "2026-03-01", "description_html": "<p>Scope</p>"},
        format="json",
    )

    milestone: db_models.Milestone = db_models.Milestone.objects.get()
    assert (response.status_code, response.json()) == (
        201,
        get_milestone_body(
            milestone,
            title="Beta",
            target_date="2026-03-01",
            description_html="<p>Scope</p>",
            project=str(project.id),
            created_by=str(create_user.id),
        ),
    )


def test_create_milestone_removes_unsafe_html_from_description(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    session_client.post(
        get_url(project, "milestones/"),
        {"title": "Beta", "description_html": "<p>Scope</p><script>alert(1)</script>"},
        format="json",
    )

    assert db_models.Milestone.objects.get().description_html == "<p>Scope</p>"


def test_create_milestone_with_title_used_in_the_project_is_rejected(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    db_models.Milestone.objects.create(project=project, title="Beta")
    db_models.Milestone.objects.create(project=other_project, title="Gamma")

    responses: t.List[api_response.Response] = [
        session_client.post(get_url(project, "milestones/"), {"title": title}, format="json")
        for title in ("Beta", "Gamma")
    ]

    assert [(response.status_code, response.json().get("title")) for response in responses] == [
        (400, ["Milestone with the same title already exists in the project"]),
        (201, "Gamma"),
    ]


def test_update_milestone(project: db_models.Project, session_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(
        project=project, title="Beta", target_date="2026-03-01"
    )
    create_issue(project, "A", milestone=milestone)

    response: api_response.Response = session_client.patch(
        get_url(project, f"milestones/{milestone.id}/"), {"title": "Beta 2", "target_date": None}, format="json"
    )

    milestone.refresh_from_db()
    assert (response.status_code, response.json()) == (
        200,
        get_milestone_body(milestone, title="Beta 2", target_date=None, total_issues=1),
    )


def test_update_milestone_keeps_its_own_title(project: db_models.Project, session_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")

    response: api_response.Response = session_client.patch(
        get_url(project, f"milestones/{milestone.id}/"), {"title": "Beta", "target_date": "2026-03-01"}, format="json"
    )

    assert (response.status_code, response.json()["target_date"]) == (200, "2026-03-01")


def test_retrieve_milestone_counts_completed_and_cancelled_work_items(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    group: str
    states: t.Dict[str, db_models.State] = {
        group: db_models.State.objects.create(project=project, name=group, group=group)
        for group in ("started", "completed", "cancelled")
    }
    for group in ("started", "completed", "completed", "cancelled"):
        create_issue(project, group, milestone=milestone, state=states[group])
    create_issue(project, "Not linked", state=states["completed"])

    response: api_response.Response = session_client.get(get_url(project, f"milestones/{milestone.id}/"))

    assert (response.status_code, response.json()) == (
        200,
        get_milestone_body(milestone, total_issues=4, completed_issues=2, cancelled_issues=1),
    )


def test_retrieve_milestone_does_not_count_archived_work_items(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    completed: db_models.State = db_models.State.objects.create(project=project, name="Done", group="completed")
    create_issue(project, "Completed", milestone=milestone, state=completed)
    create_issue(project, "Archived", milestone=milestone, state=completed, archived_at=datetime.date(2026, 1, 1))

    response: api_response.Response = session_client.get(get_url(project, f"milestones/{milestone.id}/"))

    assert (response.status_code, response.json()) == (
        200,
        get_milestone_body(milestone, total_issues=1, completed_issues=1),
    )


def test_list_milestones_by_target_date_with_undated_last(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    undated: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Undated")
    later: db_models.Milestone = db_models.Milestone.objects.create(
        project=project, title="Later", target_date="2026-06-01"
    )
    sooner: db_models.Milestone = db_models.Milestone.objects.create(
        project=project, title="Sooner", target_date="2026-03-01"
    )
    db_models.Milestone.objects.create(project=other_project, title="Other project")
    milestone: db_models.Milestone
    for milestone in (undated, later, sooner):
        milestone.refresh_from_db()

    response: api_response.Response = session_client.get(get_url(project, "milestones/"))

    assert (response.status_code, response.json()["results"]) == (
        200,
        [
            get_milestone_body(sooner, target_date="2026-03-01"),
            get_milestone_body(later, target_date="2026-06-01"),
            get_milestone_body(undated),
        ],
    )


@pytest.mark.usefixtures("inline_issue_activity")
def test_delete_milestone_unlinks_its_work_items(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    kept: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Kept")
    create_issue(project, "A", milestone=milestone)
    create_issue(project, "B", milestone=kept)

    response: api_response.Response = session_client.delete(get_url(project, f"milestones/{milestone.id}/"))

    assert response.status_code == 204, response.content
    assert list(db_models.Milestone.objects.values_list("title", flat=True)) == ["Kept"]
    assert dict(db_models.Issue.objects.values_list("name", "milestone_id")) == {"A": None, "B": kept.id}
    assert get_activities() == {("A", "milestone", "Beta", None)}


@pytest.mark.usefixtures("inline_issue_activity")
def test_add_work_items_moves_them_from_their_milestone(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    previous: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Alpha")
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B", milestone=previous)
    c: db_models.Issue = create_issue(project, "C", milestone=milestone)
    create_issue(project, "D", milestone=previous)

    response: api_response.Response = session_client.post(
        get_url(project, f"milestones/{milestone.id}/work-items/"),
        {"issues": [str(a.id), str(b.id), str(c.id)]},
        format="json",
    )

    assert response.status_code == 204, response.content
    assert dict(db_models.Issue.objects.values_list("name", "milestone_id")) == {
        "A": milestone.id,
        "B": milestone.id,
        "C": milestone.id,
        "D": previous.id,
    }
    assert get_activities() == {("A", "milestone", None, "Beta"), ("B", "milestone", "Alpha", "Beta")}


@pytest.mark.usefixtures("inline_issue_activity")
def test_add_work_items_notifies_subscribers_of_the_work_item(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    subscriber: db_models.User = db_models.User.objects.create(email="subscriber@plane.so", username="subscriber")
    db_models.ProjectMember.objects.create(project=project, member=subscriber, role=15)
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    issue: db_models.Issue = create_issue(
        project, "A", state=db_models.State.objects.create(project=project, name="Todo", group="unstarted")
    )
    db_models.IssueSubscriber.objects.create(project=project, issue=issue, subscriber=subscriber)

    with mock.patch.object(notification_task.notifications, "delay", side_effect=notification_task.notifications.run):
        session_client.post(
            get_url(project, f"milestones/{milestone.id}/work-items/"), {"issues": [str(issue.id)]}, format="json"
        )

    assert list(db_models.Notification.objects.values_list("receiver_id", "entity_identifier", "title")) == [
        (subscriber.id, issue.id, "updated the milestone to")
    ]


@pytest.mark.parametrize(
    "outsider",
    [
        pytest.param("unknown", id="unknown-work-item"),
        pytest.param("other_project", id="work-item-of-another-project"),
        pytest.param("archived", id="archived-work-item"),
    ],
)
def test_add_work_items_with_one_outside_the_project_links_none(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient, outsider: str
) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    a: db_models.Issue = create_issue(project, "A")
    outsider_ids: t.Dict[str, uuid.UUID] = {
        "unknown": uuid.uuid4(),
        "other_project": create_issue(other_project, "Other").id,
        "archived": create_issue(project, "Archived", archived_at=datetime.date(2026, 1, 1)).id,
    }

    response: api_response.Response = session_client.post(
        get_url(project, f"milestones/{milestone.id}/work-items/"),
        {"issues": [str(a.id), str(outsider_ids[outsider])]},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"issues": "Every work item must be in the project of the milestone"},
    )
    assert not db_models.Issue.objects.filter(milestone__isnull=False).exists()


def test_add_work_items_to_milestone_of_another_project_is_not_found(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=other_project, title="Beta")
    a: db_models.Issue = create_issue(project, "A")

    response: api_response.Response = session_client.post(
        get_url(project, f"milestones/{milestone.id}/work-items/"), {"issues": [str(a.id)]}, format="json"
    )

    assert response.status_code == 404, response.content
    assert dict(db_models.Issue.objects.values_list("name", "milestone_id")) == {"A": None}


@pytest.mark.usefixtures("inline_issue_activity")
def test_remove_work_items_unlinks_those_of_the_milestone(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    other: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Alpha")
    a: db_models.Issue = create_issue(project, "A", milestone=milestone)
    b: db_models.Issue = create_issue(project, "B", milestone=other)
    create_issue(project, "C", milestone=milestone)

    response: api_response.Response = session_client.delete(
        get_url(project, f"milestones/{milestone.id}/work-items/"), {"issues": [str(a.id), str(b.id)]}, format="json"
    )

    assert response.status_code == 204, response.content
    assert dict(db_models.Issue.objects.values_list("name", "milestone_id")) == {
        "A": None,
        "B": other.id,
        "C": milestone.id,
    }
    assert get_activities() == {("A", "milestone", "Beta", None)}


def test_list_work_items_of_milestone(project: db_models.Project, session_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    a: db_models.Issue = create_issue(project, "A", milestone=milestone)
    create_issue(project, "B")

    response: api_response.Response = session_client.get(get_url(project, f"milestones/{milestone.id}/work-items/"))

    assert (response.status_code, response.json()["results"]) == (
        200,
        [{"id": str(a.id), "issue": str(a.id), "milestone": str(milestone.id)}],
    )


def test_guest_reads_milestones_but_does_not_change_them(
    project: db_models.Project, create_user: db_models.User, session_client: api_test.APIClient
) -> None:
    db_models.ProjectMember.objects.filter(project=project, member=create_user).update(role=5)
    url: str = get_url(project, "milestones/")

    statuses: t.List[int] = [
        session_client.get(url).status_code,
        session_client.post(url, {"title": "Beta"}, format="json").status_code,
    ]

    assert statuses == [200, 403]


def test_project_update_switches_milestone_view(project: db_models.Project, session_client: api_test.APIClient) -> None:
    url: str = f"/api/workspaces/{project.workspace.slug}/projects/"

    response: api_response.Response = session_client.patch(
        f"{url}{project.id}/", {"milestone_view": True}, format="json"
    )

    assert response.status_code == 200, response.content
    assert [row["milestone_view"] for row in session_client.get(url).json()] == [True]


@pytest.mark.usefixtures("inline_issue_activity")
def test_issue_update_moves_it_to_milestone_and_records_activity(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    previous: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Alpha")
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    issue: db_models.Issue = create_issue(project, "A", milestone=previous)

    response: api_response.Response = session_client.patch(
        get_url(project, f"issues/{issue.id}/"), {"milestone_id": str(milestone.id)}, format="json"
    )

    assert response.status_code == 204, response.content
    assert dict(db_models.Issue.objects.values_list("name", "milestone_id")) == {"A": milestone.id}
    assert get_activities() == {("A", "milestone", "Alpha", "Beta")}


@pytest.mark.parametrize(
    "filters, expected",
    [
        pytest.param({"milestone_id": "{beta}"}, {"In Beta"}, id="one-milestone"),
        pytest.param({"milestone_id__in": "{alpha},{beta}"}, {"In Alpha", "In Beta"}, id="several-milestones"),
        pytest.param({"milestone_id__isnull": True}, {"In none"}, id="no-milestone"),
        pytest.param(
            {"or": [{"milestone_id__isnull": True}, {"milestone_id": "{beta}"}]},
            {"In none", "In Beta"},
            id="no-milestone-or-one-milestone",
        ),
    ],
)
def test_issue_list_filters_by_milestone(
    project: db_models.Project, session_client: api_test.APIClient, filters: JsonObject, expected: t.Set[str]
) -> None:
    alpha: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Alpha")
    beta: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    create_issue(project, "In Alpha", milestone=alpha)
    create_issue(project, "In Beta", milestone=beta)
    create_issue(project, "In none")

    response: api_response.Response = session_client.get(
        get_url(project, "issues/"),
        {"filters": json.dumps(filters).replace("{alpha}", str(alpha.id)).replace("{beta}", str(beta.id))},
    )

    assert response.status_code == 200, response.content
    assert {issue["name"] for issue in response.json()["results"]} == expected


@pytest.mark.parametrize(
    "milestone, expected",
    [
        pytest.param("{beta}", {"In Beta"}, id="one-milestone"),
        pytest.param("None", {"In none"}, id="no-milestone"),
    ],
)
def test_issue_list_pages_one_milestone_group(
    project: db_models.Project, session_client: api_test.APIClient, milestone: str, expected: t.Set[str]
) -> None:
    beta: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    create_issue(project, "In Beta", milestone=beta)
    create_issue(project, "In none")

    response: api_response.Response = session_client.get(
        get_url(project, "issues/"), {"milestone": milestone.replace("{beta}", str(beta.id))}
    )

    assert response.status_code == 200, response.content
    assert {issue["name"] for issue in response.json()["results"]} == expected


def test_issue_list_orders_by_milestone_title(project: db_models.Project, session_client: api_test.APIClient) -> None:
    create_issue(project, "In Beta", milestone=db_models.Milestone.objects.create(project=project, title="Beta"))
    create_issue(project, "In Alpha", milestone=db_models.Milestone.objects.create(project=project, title="Alpha"))

    response: api_response.Response = session_client.get(get_url(project, "issues/"), {"order_by": "milestone__title"})

    assert response.status_code == 200, response.content
    assert [issue["name"] for issue in response.json()["results"]] == ["In Alpha", "In Beta"]


def test_issue_list_groups_by_milestone(project: db_models.Project, session_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    empty: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Empty")
    create_issue(project, "A", milestone=milestone)
    create_issue(project, "B")

    response: api_response.Response = session_client.get(get_url(project, "issues/"), {"group_by": "milestone_id"})

    assert response.status_code == 200, response.content
    assert {
        key: [issue["name"] for issue in group["results"]] for key, group in response.json()["results"].items()
    } == {str(milestone.id): ["A"], str(empty.id): [], "None": ["B"]}


def test_issue_search_with_milestone_lists_work_items_in_no_milestone(
    project: db_models.Project, session_client: api_test.APIClient
) -> None:
    create_issue(project, "In Beta", milestone=db_models.Milestone.objects.create(project=project, title="Beta"))
    create_issue(project, "In none")

    response: api_response.Response = session_client.get(get_url(project, "search-issues/"), {"milestone": "true"})

    assert response.status_code == 200, response.content
    assert [issue["name"] for issue in response.json()] == ["In none"]


def test_issue_with_milestone_of_another_project_is_rejected(
    project: db_models.Project, other_project: db_models.Project, session_client: api_test.APIClient
) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=other_project, title="Elsewhere")

    response: api_response.Response = session_client.post(
        get_url(project, "issues/"), {"name": "A", "milestone_id": str(milestone.id)}, format="json"
    )

    assert (response.status_code, response.json()) == (
        400,
        {"non_field_errors": ["Milestone is not valid please pass a valid milestone_id"]},
    )
