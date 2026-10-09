# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import datetime
import typing as t
import unittest.mock as mock

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


def get_page(results: t.List[JsonObject]) -> JsonObject:
    """The pagination envelope the SDK requires around the only page of a list."""
    return {
        "grouped_by": None,
        "sub_grouped_by": None,
        "total_count": len(results),
        "next_cursor": "1000:1:0",
        "prev_cursor": "1000:-1:1",
        "next_page_results": False,
        "prev_page_results": False,
        "count": len(results),
        "total_pages": 1 if results else 0,
        "total_results": len(results),
        "extra_stats": None,
        "results": results,
    }


def test_list_milestones(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    milestone.refresh_from_db()

    response: api_response.Response = api_key_client.get(get_url(project, "milestones/"))

    assert (response.status_code, response.json()) == (200, get_page([get_milestone_body(milestone)]))


def test_create_milestone(
    project: db_models.Project, create_user: db_models.User, api_key_client: api_test.APIClient
) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, "milestones/"),
        {"title": "Beta", "target_date": "2026-03-01", "external_source": "jira", "external_id": "10001"},
        format="json",
    )

    milestone: db_models.Milestone = db_models.Milestone.objects.get()
    assert (response.status_code, response.json()) == (
        201,
        get_milestone_body(
            milestone,
            title="Beta",
            target_date="2026-03-01",
            external_source="jira",
            external_id="10001",
            project=str(project.id),
            created_by=str(create_user.id),
        ),
    )


def test_retrieve_milestone(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    milestone.refresh_from_db()

    response: api_response.Response = api_key_client.get(get_url(project, f"milestones/{milestone.id}/"))

    assert (response.status_code, response.json()) == (200, get_milestone_body(milestone))


def test_update_milestone(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")

    response: api_response.Response = api_key_client.patch(
        get_url(project, f"milestones/{milestone.id}/"), {"title": "Beta 2", "target_date": "2026-03-01"}, format="json"
    )

    milestone.refresh_from_db()
    assert (response.status_code, response.json()) == (
        200,
        get_milestone_body(milestone, title="Beta 2", target_date="2026-03-01"),
    )


def test_delete_milestone(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")

    response: api_response.Response = api_key_client.delete(get_url(project, f"milestones/{milestone.id}/"))

    assert (response.status_code, response.content) == (204, b"")
    assert not db_models.Milestone.objects.exists()


def test_list_work_items_of_milestone(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    issue: db_models.Issue = db_models.Issue.objects.create(project=project, name="A", milestone=milestone)

    response: api_response.Response = api_key_client.get(get_url(project, f"milestones/{milestone.id}/work-items/"))

    assert (response.status_code, response.json()) == (
        200,
        get_page([{"id": str(issue.id), "issue": str(issue.id), "milestone": str(milestone.id)}]),
    )


def test_add_work_items_to_milestone(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    issue: db_models.Issue = db_models.Issue.objects.create(project=project, name="A")

    response: api_response.Response = api_key_client.post(
        get_url(project, f"milestones/{milestone.id}/work-items/"), {"issues": [str(issue.id)]}, format="json"
    )

    assert (response.status_code, response.content) == (204, b"")
    assert dict(db_models.Issue.objects.values_list("name", "milestone_id")) == {"A": milestone.id}


def test_remove_work_items_from_milestone(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    issue: db_models.Issue = db_models.Issue.objects.create(project=project, name="A", milestone=milestone)

    response: api_response.Response = api_key_client.delete(
        get_url(project, f"milestones/{milestone.id}/work-items/"), {"issues": [str(issue.id)]}, format="json"
    )

    assert (response.status_code, response.content) == (204, b"")
    assert dict(db_models.Issue.objects.values_list("name", "milestone_id")) == {"A": None}


@pytest.mark.usefixtures("inline_issue_activity")
def test_work_item_update_moves_it_to_milestone_and_records_activity(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    previous: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Alpha")
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=project, title="Beta")
    issue: db_models.Issue = db_models.Issue.objects.create(project=project, name="A", milestone=previous)

    response: api_response.Response = api_key_client.patch(
        get_url(project, f"work-items/{issue.id}/"), {"milestone_id": str(milestone.id)}, format="json"
    )

    assert response.status_code == 200, response.content
    assert dict(db_models.Issue.objects.values_list("name", "milestone_id")) == {"A": milestone.id}
    assert set(db_models.IssueActivity.objects.values_list("issue__name", "field", "old_value", "new_value")) == {
        ("A", "milestone", "Alpha", "Beta")
    }


def test_work_item_with_milestone_of_another_project_is_rejected(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    other_project: db_models.Project = db_models.Project.objects.create(
        name="Other", identifier="OTH", workspace=project.workspace
    )
    milestone: db_models.Milestone = db_models.Milestone.objects.create(project=other_project, title="Elsewhere")

    response: api_response.Response = api_key_client.post(
        get_url(project, "work-items/"), {"name": "A", "milestone_id": str(milestone.id)}, format="json"
    )

    assert (response.status_code, response.json()) == (
        400,
        {"non_field_errors": ["Milestone is not valid please pass a valid milestone_id"]},
    )
