# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties

pytestmark = [pytest.mark.django_db, pytest.mark.contract]


@pytest.fixture(name="project")
def create_project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(name="Features", identifier="FT", workspace=workspace)
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=20)
    return project


def get_project_features_url(project: db_models.Project) -> str:
    return f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/features/"


def test_get_project_features(project: db_models.Project, api_key_client: api_test.APIClient) -> None:
    response: api_response.Response = api_key_client.get(get_project_features_url(project))

    assert (response.status_code, response.json()) == (
        200,
        {
            "modules": False,
            "cycles": False,
            "views": False,
            "pages": True,
            "intakes": False,
            "milestones": False,
            "work_item_types": False,
        },
    )


def test_patch_project_features_changes_only_the_sent_ones(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    response: api_response.Response = api_key_client.patch(
        get_project_features_url(project), {"cycles": True, "milestones": True}, format="json"
    )

    assert (response.status_code, response.json()) == (
        200,
        {
            "modules": False,
            "cycles": True,
            "views": False,
            "pages": True,
            "intakes": False,
            "milestones": True,
            "work_item_types": False,
        },
    )


def test_enabling_intakes_creates_the_default_intake_of_the_project(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    response: api_response.Response = api_key_client.patch(
        get_project_features_url(project), {"intakes": True}, format="json"
    )

    actual: t.List[t.Tuple[str, bool]] = list(
        db_models.Intake.objects.filter(project=project).values_list("name", "is_default")
    )
    assert (response.status_code, actual) == (200, [("Features Intake", True)])


def test_patch_project_features_keeps_the_default_intake_of_a_project_with_intakes(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    api_key_client.patch(get_project_features_url(project), {"intakes": True}, format="json")

    response: api_response.Response = api_key_client.patch(
        get_project_features_url(project), {"cycles": True}, format="json"
    )

    actual: t.List[t.Tuple[str, bool]] = list(
        db_models.Intake.objects.filter(project=project).values_list("name", "is_default")
    )
    assert (response.status_code, actual) == (200, [("Features Intake", True)])


def test_enabling_work_item_types_creates_the_default_types(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    response: api_response.Response = api_key_client.patch(
        get_project_features_url(project), {"work_item_types": True}, format="json"
    )

    actual: t.List[t.Tuple[str, bool]] = sorted(
        custom_properties.get_project_issue_types(project.id).values_list("name", "is_default")
    )
    assert (response.status_code, actual) == (200, [("Epic", False), ("Task", True)])


def test_work_item_types_cannot_be_disabled_again(
    project: db_models.Project, api_key_client: api_test.APIClient
) -> None:
    api_key_client.patch(get_project_features_url(project), {"work_item_types": True}, format="json")

    response: api_response.Response = api_key_client.patch(
        get_project_features_url(project), {"work_item_types": False}, format="json"
    )

    assert (response.status_code, response.json()) == (
        400,
        {"work_item_types": ["Work item types cannot be disabled once enabled."]},
    )


def test_get_workspace_features(workspace: db_models.Workspace, api_key_client: api_test.APIClient) -> None:
    response: api_response.Response = api_key_client.get(f"/api/v1/workspaces/{workspace.slug}/features/")

    assert (response.status_code, response.json()) == (200, {"wiki": True})


def test_patch_workspace_features_switches_the_wiki(
    workspace: db_models.Workspace, api_key_client: api_test.APIClient
) -> None:
    response: api_response.Response = api_key_client.patch(
        f"/api/v1/workspaces/{workspace.slug}/features/", {"wiki": False}, format="json"
    )

    workspace.refresh_from_db()
    assert (response.status_code, response.json(), workspace.is_wiki_enabled) == (200, {"wiki": False}, False)
