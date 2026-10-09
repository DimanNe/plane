# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import typing as t

import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties

pytestmark: t.List[pytest.MarkDecorator] = [pytest.mark.django_db, pytest.mark.contract]

PropertyType: t.TypeAlias = db_models.IssueProperty.PropertyType
JsonObject: t.TypeAlias = t.Dict[str, t.Any]


def get_url(project: db_models.Project, path: str) -> str:
    return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/{path}"


def fill_in(filters: JsonObject, names: t.Dict[str, str]) -> JsonObject:
    """Returns the filters with every {name} replaced by what the fixture created under that name."""
    text: str = json.dumps(filters)
    name: str
    value: str
    for name, value in names.items():
        text = text.replace(f"{{{name}}}", value)
    return json.loads(text)


@pytest.fixture
def project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(
        workspace=workspace, name="Typed", identifier="TY", is_issue_type_enabled=True
    )
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=20)
    custom_properties.enable_project_types(project)
    return project


@pytest.fixture
def names(
    session_client: api_test.APIClient, project: db_models.Project, create_user: db_models.User
) -> t.Dict[str, str]:
    """
    Tasks One, Two and Three and an epic, named Epic, which has none of the properties of a task.

    | Task  | Severity | Tags      | Reviewer | Needs QA | Release date |
    | One   | High     | Red       | me       | yes      | 2026-01-10   |
    | Two   | Critical | Red, Blue | teammate | no       | 2026-02-20   |
    | Three |          |           |          |          | 2026-03-05   |

    Returns the condition key of each property and the id of each option and member, by name.
    """
    teammate: db_models.User = db_models.User.objects.create(email="teammate@plane.so", username="teammate")
    db_models.WorkspaceMember.objects.create(workspace=project.workspace, member=teammate, role=15)
    db_models.ProjectMember.objects.create(project=project, member=teammate, role=15)
    names: t.Dict[str, str] = {"me": str(create_user.id), "teammate": str(teammate.id)}

    task: db_models.IssueType = custom_properties.get_project_issue_types(project.id).get(name="Task")
    ids: t.Dict[str, str] = {}
    name: str
    fields: JsonObject
    for name, fields in {
        "severity": {"property_type": PropertyType.OPTION},
        "tags": {"property_type": PropertyType.OPTION, "is_multi": True},
        "reviewer": {"property_type": PropertyType.RELATION, "relation_type": "USER"},
        "needs_qa": {"property_type": PropertyType.BOOLEAN},
        "release_date": {"property_type": PropertyType.DATETIME},
    }.items():
        ids[name] = str(
            db_models.IssueProperty.objects.create(project=project, issue_type=task, display_name=name, **fields).id
        )
        names[name] = f"customproperty_{ids[name]}"
    property_name: str
    for name, property_name in (("high", "severity"), ("critical", "severity"), ("red", "tags"), ("blue", "tags")):
        names[name] = str(
            db_models.IssuePropertyOption.objects.create(project=project, property_id=ids[property_name], name=name).id
        )

    epic: db_models.IssueType = custom_properties.get_project_issue_types(project.id).get(name="Epic")
    work_item: JsonObject
    for work_item in (
        {
            "name": "One",
            "custom_properties": {
                ids["severity"]: names["high"],
                ids["tags"]: [names["red"]],
                ids["reviewer"]: names["me"],
                ids["needs_qa"]: True,
                ids["release_date"]: "2026-01-10",
            },
        },
        {
            "name": "Two",
            "custom_properties": {
                ids["severity"]: names["critical"],
                ids["tags"]: [names["red"], names["blue"]],
                ids["reviewer"]: names["teammate"],
                ids["needs_qa"]: False,
                ids["release_date"]: "2026-02-20",
            },
        },
        {"name": "Three", "custom_properties": {ids["release_date"]: "2026-03-05"}},
        {"name": "Epic", "type_id": str(epic.id)},
    ):
        response: api_response.Response = session_client.post(get_url(project, "issues/"), work_item, format="json")
        assert response.status_code == 201, response.data
    return names


@pytest.mark.parametrize(
    "filters, expected",
    [
        pytest.param({"{severity}__in": "{high}"}, {"One"}, id="dropdown-is"),
        pytest.param({"{severity}__in": "{high},{critical}"}, {"One", "Two"}, id="dropdown-is-any-of"),
        pytest.param({"{tags}__in": "{blue}"}, {"Two"}, id="multi-select-dropdown-is"),
        pytest.param({"{tags}__in": "{red},{blue}"}, {"One", "Two"}, id="multi-select-dropdown-is-any-of"),
        pytest.param({"{reviewer}__in": "{teammate}"}, {"Two"}, id="member-is"),
        pytest.param({"{reviewer}__in": "{me},{teammate}"}, {"One", "Two"}, id="member-is-any-of"),
        pytest.param({"{needs_qa}__exact": "true"}, {"One"}, id="boolean-is-yes"),
        pytest.param({"{needs_qa}__exact": "false"}, {"Two", "Three"}, id="boolean-is-no-for-its-type-only"),
        pytest.param({"{release_date}__exact": "2026-02-20"}, {"Two"}, id="date-is"),
        pytest.param({"{release_date}__range": "2026-01-10,2026-03-04"}, {"One", "Two"}, id="date-between"),
        pytest.param(
            {"and": [{"{severity}__in": "{high},{critical}"}, {"{needs_qa}__exact": "false"}]},
            {"Two"},
            id="two-conditions",
        ),
        pytest.param({"not": {"{tags}__in": "{red}"}}, {"Three", "Epic"}, id="not-any-of"),
        pytest.param({"not": {"{release_date}__range": "2026-01-10,2026-03-04"}}, {"Three", "Epic"}, id="not-between"),
    ],
)
def test_work_item_list_is_filtered_by_custom_property(
    session_client: api_test.APIClient,
    project: db_models.Project,
    names: t.Dict[str, str],
    filters: JsonObject,
    expected: t.Set[str],
) -> None:
    response: api_response.Response = session_client.get(
        get_url(project, "issues/"), {"filters": json.dumps(fill_in(filters, names))}
    )

    assert response.status_code == 200, response.data
    assert {work_item["name"] for work_item in response.data["results"]} == expected


def test_condition_on_a_deleted_custom_property_matches_no_work_item(
    session_client: api_test.APIClient, project: db_models.Project, names: t.Dict[str, str]
) -> None:
    db_models.IssueProperty.objects.get(display_name="release_date").delete()

    response: api_response.Response = session_client.get(
        get_url(project, "issues/"), {"filters": json.dumps({f"{names['release_date']}__exact": "2026-02-20"})}
    )

    assert (response.status_code, response.data["results"]) == (200, [])


@pytest.mark.parametrize(
    "key, expected",
    [
        pytest.param(
            "{severity}__gt",
            {"message": "Filtering on field 'customproperty_value__gt' is not allowed", "code": "invalid_filter_field"},
            id="lookup-the-web-does-not-send",
        ),
        pytest.param("customproperty_severity__in", {"error": "Please provide valid detail"}, id="no-property-id"),
    ],
)
def test_unusable_custom_property_condition_is_refused(
    session_client: api_test.APIClient,
    project: db_models.Project,
    names: t.Dict[str, str],
    key: str,
    expected: JsonObject,
) -> None:
    response: api_response.Response = session_client.get(
        get_url(project, "issues/"), {"filters": json.dumps(fill_in({key: "{high}"}, names))}
    )

    assert (response.status_code, response.json()) == (400, expected)
