# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import datetime
import typing as t
import unittest.mock as mock
import uuid

import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.bgtasks.issue_activities_task as issue_activities_task
import plane.db.models as db_models

pytestmark = [pytest.mark.django_db, pytest.mark.contract]

JsonObject: t.TypeAlias = t.Dict[str, t.Any]


@pytest.fixture(name="project")
def create_project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(name="Timeline", identifier="TL", workspace=workspace)
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
    return f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/{path}"


def create_issue(project: db_models.Project, name: str) -> db_models.Issue:
    issue: db_models.Issue = db_models.Issue.objects.create(project=project, name=name)
    issue.refresh_from_db()
    return issue


def create_relation(issue: db_models.Issue, relation_type: str, related_issue: db_models.Issue) -> None:
    db_models.IssueRelation.objects.create(
        project=issue.project, issue=issue, relation_type=relation_type, related_issue=related_issue
    )


def get_relations() -> t.Set[t.Tuple[str, uuid.UUID, uuid.UUID]]:
    return set(db_models.IssueRelation.objects.values_list("relation_type", "issue_id", "related_issue_id"))


def get_activities() -> t.Set[t.Tuple[str, str, str, str, str]]:
    """Work item name, verb, field, old and new value of every recorded activity."""
    return set(db_models.IssueActivity.objects.values_list("issue__name", "verb", "field", "old_value", "new_value"))


def format_timestamp(value: datetime.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def get_work_item_body(issue: db_models.Issue, relation_type: str) -> JsonObject:
    return {
        "id": str(issue.id),
        "name": issue.name,
        "sequence_id": issue.sequence_id,
        "project_id": str(issue.project_id),
        "state_id": None,
        "priority": "none",
        "type_id": None,
        "sort_order": issue.sort_order,
        "created_at": format_timestamp(issue.created_at),
        "updated_at": format_timestamp(issue.updated_at),
        "created_by": None,
        "updated_by": None,
        "relation_type": relation_type,
    }


def test_list_dependencies_groups_work_items_by_relation_read_from_the_work_item(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    issues: t.Dict[str, db_models.Issue] = {name: create_issue(project, name) for name in "ABCDEFGH"}
    create_relation(issues["B"], "blocked_by", issues["A"])
    create_relation(issues["A"], "blocked_by", issues["C"])
    create_relation(issues["A"], "start_before", issues["D"])
    create_relation(issues["E"], "start_before", issues["A"])
    create_relation(issues["A"], "finish_before", issues["F"])
    create_relation(issues["G"], "finish_before", issues["A"])
    create_relation(issues["A"], "relates_to", issues["H"])

    response: api_response.Response = api_key_client.get(get_url(project, f"work-items/{issues['A'].id}/dependencies/"))

    assert (response.status_code, response.json()) == (
        200,
        {
            "blocking": [get_work_item_body(issues["B"], "blocking")],
            "blocked_by": [get_work_item_body(issues["C"], "blocked_by")],
            "start_before": [get_work_item_body(issues["D"], "start_before")],
            "start_after": [get_work_item_body(issues["E"], "start_after")],
            "finish_before": [get_work_item_body(issues["F"], "finish_before")],
            "finish_after": [get_work_item_body(issues["G"], "finish_after")],
        },
    )


def test_create_dependency(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")

    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{a.id}/dependencies/"),
        {"relation_type": "blocking", "work_item_ids": [str(b.id)]},
        format="json",
    )

    assert (response.status_code, response.json()) == (201, [get_work_item_body(b, "blocking")])
    assert get_relations() == {("blocked_by", b.id, a.id)}


def test_create_dependency_that_closes_a_cycle_is_rejected(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    create_relation(b, "blocked_by", a)

    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{b.id}/dependencies/"),
        {"relation_type": "start_before", "work_item_ids": [str(a.id)]},
        format="json",
    )

    assert (response.status_code, response.json()) == (400, {"error": "This dependency would create a cycle"})
    assert get_relations() == {("blocked_by", b.id, a.id)}


def test_create_dependency_of_other_relation_type_is_rejected(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")

    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{a.id}/dependencies/"),
        {"relation_type": "relates_to", "work_item_ids": [str(b.id)]},
        format="json",
    )

    assert response.status_code == 400, response.content
    assert get_relations() == set()


@pytest.mark.parametrize(
    "issue_name, related_issue_name",
    [pytest.param("A", "B", id="from-the-predecessor"), pytest.param("B", "A", id="from-the-dependent")],
)
def test_remove_dependency(
    project: db_models.Project, api_key_client: api_test.APIClient, issue_name: str, related_issue_name: str
) -> None:
    issues: t.Dict[str, db_models.Issue] = {name: create_issue(project, name) for name in "ABC"}
    create_relation(issues["B"], "blocked_by", issues["A"])
    create_relation(issues["C"], "blocked_by", issues["A"])

    response: api_response.Response = api_key_client.delete(
        get_url(project, f"work-items/{issues[issue_name].id}/dependencies/{issues[related_issue_name].id}/")
    )

    assert (response.status_code, response.content) == (204, b"")
    assert get_relations() == {("blocked_by", issues["C"].id, issues["A"].id)}


def test_remove_dependency_does_not_remove_other_relation(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    create_relation(a, "relates_to", b)

    response: api_response.Response = api_key_client.delete(get_url(project, f"work-items/{a.id}/dependencies/{b.id}/"))

    assert (response.status_code, response.json()) == (404, {"error": "These work items have no dependency"})
    assert get_relations() == {("relates_to", a.id, b.id)}


def test_create_dependency_of_another_type_between_the_same_work_items_is_rejected(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    create_relation(a, "start_before", b)

    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{a.id}/dependencies/"),
        {"relation_type": "finish_before", "work_item_ids": [str(b.id)]},
        format="json",
    )

    assert (response.status_code, response.json()) == (400, {"error": "These work items already have a dependency"})
    assert get_relations() == {("start_before", a.id, b.id)}


@pytest.mark.parametrize(
    "outsider",
    [pytest.param("unknown", id="unknown-work-item"), pytest.param("archived", id="archived-work-item")],
)
def test_create_dependency_with_a_work_item_that_cannot_be_linked_links_none(
    project: db_models.Project, api_key_client: api_test.APIClient, outsider: str
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    outsider_ids: t.Dict[str, uuid.UUID] = {
        "unknown": uuid.uuid4(),
        "archived": db_models.Issue.objects.create(
            project=project, name="Archived", archived_at=datetime.date(2026, 1, 1)
        ).id,
    }

    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{a.id}/dependencies/"),
        {"relation_type": "blocking", "work_item_ids": [str(b.id), str(outsider_ids[outsider])]},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"work_item_ids": "Every work item must be in the workspace and not archived"},
    )
    assert get_relations() == set()


def test_remove_dependency_keeps_other_relation_between_the_same_work_items(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    create_relation(b, "blocked_by", a)
    create_relation(a, "relates_to", b)

    response: api_response.Response = api_key_client.delete(get_url(project, f"work-items/{a.id}/dependencies/{b.id}/"))

    assert (response.status_code, response.content) == (204, b"")
    assert get_relations() == {("relates_to", a.id, b.id)}


@pytest.mark.usefixtures("inline_issue_activity")
def test_create_dependency_records_activity_on_both_work_items(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")

    api_key_client.post(
        get_url(project, f"work-items/{a.id}/dependencies/"),
        {"relation_type": "blocking", "work_item_ids": [str(b.id)]},
        format="json",
    )

    assert get_activities() == {("A", "updated", "blocking", "", "TL-2"), ("B", "updated", "blocked_by", "", "TL-1")}


@pytest.mark.usefixtures("inline_issue_activity")
def test_remove_dependency_records_activity_on_both_work_items(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")
    create_relation(b, "blocked_by", a)

    api_key_client.delete(get_url(project, f"work-items/{b.id}/dependencies/{a.id}/"))

    assert get_activities() == {("B", "deleted", "blocked_by", "TL-1", ""), ("A", "deleted", "blocking", "TL-2", "")}


def test_list_work_item_relations_groups_relations_other_than_dependencies(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    issues: t.Dict[str, db_models.Issue] = {name: create_issue(project, name) for name in "ABCDEF"}
    create_relation(issues["A"], "relates_to", issues["B"])
    create_relation(issues["C"], "duplicate", issues["A"])
    create_relation(issues["A"], "implemented_by", issues["D"])
    create_relation(issues["E"], "implemented_by", issues["A"])
    create_relation(issues["A"], "blocked_by", issues["F"])

    response: api_response.Response = api_key_client.get(
        get_url(project, f"work-items/{issues['A'].id}/work-item-relations/")
    )

    assert (response.status_code, response.json()) == (
        200,
        {
            "relates_to": [get_work_item_body(issues["B"], "relates_to")],
            "duplicate": [get_work_item_body(issues["C"], "duplicate")],
            "implements": [get_work_item_body(issues["E"], "implements")],
            "implemented_by": [get_work_item_body(issues["D"], "implemented_by")],
        },
    )


def test_list_work_item_relation_definitions_is_an_empty_page(
    workspace: db_models.Workspace, api_key_client: api_test.APIClient
) -> None:
    response: api_response.Response = api_key_client.get(
        f"/api/v1/workspaces/{workspace.slug}/work-item-relation-definitions/", {"is_active": "true", "per_page": 100}
    )

    assert (response.status_code, response.json()) == (
        200,
        {
            "grouped_by": None,
            "sub_grouped_by": None,
            "total_count": 0,
            "next_cursor": "100:1:0",
            "prev_cursor": "100:-1:1",
            "next_page_results": False,
            "prev_page_results": False,
            "count": 0,
            "total_pages": 0,
            "total_results": 0,
            "extra_stats": None,
            "results": [],
        },
    )


def test_create_relation_through_relations_endpoint(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    a: db_models.Issue = create_issue(project, "A")
    b: db_models.Issue = create_issue(project, "B")

    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{a.id}/relations/"),
        {"relation_type": "start_after", "issues": [str(b.id)]},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert get_relations() == {("start_before", b.id, a.id)}
