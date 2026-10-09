# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.db.models as db_models
import plane.utils.grouper as grouper

pytestmark: t.List[pytest.MarkDecorator] = [pytest.mark.django_db, pytest.mark.contract]

LONG_TEXT: str = "A description that is longer than a list row is wide. " * 20


def test_work_item_lists_carry_the_start_of_the_plain_text_description(
    session_client: api_test.APIClient, workspace: db_models.Workspace, create_user: db_models.User
) -> None:
    project: db_models.Project = db_models.Project.objects.create(
        workspace=workspace, name="Described", identifier="DE"
    )
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=20)
    parent: db_models.Issue = db_models.Issue.objects.create(
        project=project, name="Long", description_html=f"<p>{LONG_TEXT}</p>"
    )
    db_models.Issue.objects.create(
        project=project, name="Short", description_html="<p>Two <strong>short</strong> words</p>", parent=parent
    )
    db_models.Issue.objects.create(
        project=project,
        name="Blocks",
        description_html="<p>First paragraph.</p><ul><li>one</li><li>two</li></ul><p>Q&amp;A<br>last</p>",
        parent=parent,
    )
    db_models.Issue.objects.create(project=project, name="Empty", parent=parent)
    url: str = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/"

    work_items: api_response.Response = session_client.get(url)
    sub_work_items: api_response.Response = session_client.get(f"{url}{parent.id}/sub-issues/")

    assert (
        {work_item["name"]: work_item["description_prefix"] for work_item in work_items.data["results"]},
        {work_item["name"]: work_item["description_prefix"] for work_item in sub_work_items.data["sub_issues"]},
    ) == (
        {
            "Long": LONG_TEXT[: grouper.DESCRIPTION_PREFIX_LENGTH],
            "Short": "Two short words",
            "Blocks": "First paragraph. one two Q&amp;A last",
            "Empty": "",
        },
        {"Short": "Two short words", "Blocks": "First paragraph. one two Q&amp;A last", "Empty": ""},
    )
