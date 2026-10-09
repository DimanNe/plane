# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t
import unittest.mock as mock

import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.bgtasks.issue_activities_task as issue_activities_task
import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties

pytestmark: t.List[pytest.MarkDecorator] = [pytest.mark.django_db, pytest.mark.contract]

PropertyType: t.TypeAlias = db_models.IssueProperty.PropertyType
RelationType: t.TypeAlias = db_models.IssueProperty.RelationType

# The bodies below are what the pydantic models of plane-sdk 0.3.1 validate: WorkItemType,
# WorkItemProperty, WorkItemPropertyOption and WorkItemPropertyValueDetail.


def get_url(project: db_models.Project, path: str) -> str:
    return f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}/{path}"


def get_type_body(issue_type: db_models.IssueType) -> t.Dict[str, t.Any]:
    return {
        "id": str(issue_type.id),
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
        "deleted_at": None,
        "name": issue_type.name,
        "description": issue_type.description,
        "logo_props": {},
        "is_epic": False,
        "is_default": issue_type.is_default,
        "is_active": issue_type.is_active,
        "level": 0.0,
        "external_source": None,
        "external_id": None,
        "created_by": issue_type.created_by_id and str(issue_type.created_by_id),
        "updated_by": issue_type.updated_by_id and str(issue_type.updated_by_id),
        "workspace": str(issue_type.workspace_id),
    }


def get_option_body(option: db_models.IssuePropertyOption) -> t.Dict[str, t.Any]:
    return {
        "id": str(option.id),
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
        "deleted_at": None,
        "name": option.name,
        "sub_level_label": option.sub_level_label,
        "sort_order": option.sort_order,
        "logo_props": {},
        "is_default": option.is_default,
        "created_by": option.created_by_id and str(option.created_by_id),
        "updated_by": option.updated_by_id and str(option.updated_by_id),
        "project": str(option.project_id),
        "workspace": str(option.workspace_id),
        "property": str(option.property_id),
        "parent": option.parent_id and str(option.parent_id),
    }


def get_property_body(property: db_models.IssueProperty) -> t.Dict[str, t.Any]:
    return {
        "id": str(property.id),
        "default_value": property.default_value,
        "options": [get_option_body(option) for option in property.options.all()],
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
        "deleted_at": None,
        "display_name": property.display_name,
        "description": property.description,
        "logo_props": {},
        "sort_order": property.sort_order,
        "property_type": property.property_type,
        "relation_type": property.relation_type,
        "is_required": property.is_required,
        "is_active": property.is_active,
        "is_multi": property.is_multi,
        "settings": property.settings,
        "created_by": property.created_by_id and str(property.created_by_id),
        "updated_by": property.updated_by_id and str(property.updated_by_id),
        "project": str(property.project_id),
        "workspace": str(property.workspace_id),
        "issue_type": str(property.issue_type_id),
    }


def get_value_body(issue: db_models.Issue, property: db_models.IssueProperty, value: t.Any) -> t.Dict[str, t.Any]:
    return {"id": str(property.id), "property_id": str(property.id), "issue_id": str(issue.id), "value": value}


@pytest.fixture
def project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(
        workspace=workspace, name="Typed", identifier="TY", is_issue_type_enabled=True
    )
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=20)
    custom_properties.enable_project_types(project)
    return project


@pytest.fixture
def task(project: db_models.Project) -> db_models.IssueType:
    return custom_properties.get_project_issue_types(project.id).get(name="Task")


@pytest.fixture
def issue(project: db_models.Project, task: db_models.IssueType) -> db_models.Issue:
    return db_models.Issue.objects.create(project=project, name="Work item", type=task)


@pytest.fixture
def dropdown(project: db_models.Project, task: db_models.IssueType) -> db_models.IssueProperty:
    property: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project, issue_type=task, display_name="Tags", property_type=PropertyType.OPTION, is_multi=True
    )
    name: str
    for name in ("Red", "Blue"):
        db_models.IssuePropertyOption.objects.create(project=project, property=property, name=name)
    return property


@pytest.fixture
def location(project: db_models.Project, task: db_models.IssueType) -> db_models.IssueProperty:
    """A cascading property with two mandatory levels: USA on the first, California under it."""
    property: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project,
        issue_type=task,
        display_name="Location",
        property_type=PropertyType.CASCADING,
        settings={"levels": [{"name": "Country", "is_required": True}, {"name": "State", "is_required": True}]},
    )
    usa: db_models.IssuePropertyOption = db_models.IssuePropertyOption.objects.create(
        project=project, property=property, name="USA"
    )
    db_models.IssuePropertyOption.objects.create(project=project, property=property, parent=usa, name="California")
    return property


# workitem_type tool


def test_types_are_listed_as_a_plain_list(
    api_key_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    response: api_response.Response = api_key_client.get(get_url(project, "work-item-types/"))

    epic: db_models.IssueType = custom_properties.get_project_issue_types(project.id).get(name="Epic")
    assert (response.status_code, response.json()) == (200, [get_type_body(task), get_type_body(epic)])


def test_type_is_created(api_key_client: api_test.APIClient, project: db_models.Project) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, "work-item-types/"),
        {"name": "Bug", "description": "A defect", "is_active": True, "project_ids": [str(project.id)]},
        format="json",
    )

    created: db_models.IssueType = custom_properties.get_project_issue_types(project.id).get(name="Bug")
    assert (response.status_code, response.json()) == (201, get_type_body(created))


def test_type_is_retrieved(
    api_key_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    response: api_response.Response = api_key_client.get(get_url(project, f"work-item-types/{task.id}/"))

    assert (response.status_code, response.json()) == (200, get_type_body(task))


def test_type_is_updated(api_key_client: api_test.APIClient, project: db_models.Project) -> None:
    epic: db_models.IssueType = custom_properties.get_project_issue_types(project.id).get(name="Epic")

    response: api_response.Response = api_key_client.patch(
        get_url(project, f"work-item-types/{epic.id}/"), {"name": "Initiative", "is_active": False}, format="json"
    )

    epic.refresh_from_db()
    assert (response.status_code, response.json(), epic.name, epic.is_active) == (
        200,
        get_type_body(epic),
        "Initiative",
        False,
    )


def test_type_is_deleted(api_key_client: api_test.APIClient, project: db_models.Project) -> None:
    epic: db_models.IssueType = custom_properties.get_project_issue_types(project.id).get(name="Epic")

    response: api_response.Response = api_key_client.delete(get_url(project, f"work-item-types/{epic.id}/"))

    assert (
        response.status_code,
        list(custom_properties.get_project_issue_types(project.id).values_list("name", flat=True)),
    ) == (204, ["Task"])


def test_project_update_enables_types(
    api_key_client: api_test.APIClient, workspace: db_models.Workspace, create_user: db_models.User
) -> None:
    plain: db_models.Project = db_models.Project.objects.create(workspace=workspace, name="Plain", identifier="PL")
    db_models.ProjectMember.objects.create(project=plain, member=create_user, role=20)

    response: api_response.Response = api_key_client.patch(
        f"/api/v1/workspaces/{workspace.slug}/projects/{plain.id}/", {"is_issue_type_enabled": True}, format="json"
    )

    assert response.status_code == 200, response.data
    assert sorted(custom_properties.get_project_issue_types(plain.id).values_list("name", "is_default")) == [
        ("Epic", False),
        ("Task", True),
    ]


# workitem_property tool: properties


def test_property_is_created_with_the_payload_the_sdk_sends(
    api_key_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/"),
        {
            "display_name": "Severity",
            "description": "How bad it is",
            "property_type": "OPTION",
            "is_required": True,
            "is_multi": False,
            "is_active": True,
            "options": [{"name": "Low"}, {"name": "High", "is_default": True}],
        },
        format="json",
    )

    created: db_models.IssueProperty = db_models.IssueProperty.objects.get(issue_type=task)
    assert (response.status_code, response.json()) == (201, get_property_body(created))
    assert [(option.name, option.is_default) for option in created.options.all()] == [("Low", False), ("High", True)]


def test_cascading_property_is_created_with_the_levels_the_sdk_cannot_send(
    api_key_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/"),
        {"display_name": "Location", "property_type": "CASCADING", "options": [{"name": "USA"}, {"name": "Canada"}]},
        format="json",
    )

    created: db_models.IssueProperty = db_models.IssueProperty.objects.get(issue_type=task)
    assert (response.status_code, response.json(), created.settings) == (
        201,
        get_property_body(created),
        {"levels": [{"name": "Level 1", "is_required": False}, {"name": "Level 2", "is_required": False}]},
    )
    assert [(option.name, option.parent) for option in created.options.all()] == [("USA", None), ("Canada", None)]


def test_text_property_takes_the_settings_the_sdk_sends(
    api_key_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/"),
        {"display_name": "Note", "property_type": "TEXT", "settings": {"display_format": "single-line"}},
        format="json",
    )

    assert (response.status_code, response.json()["settings"]) == (201, {"display_format": "single-line"})


@pytest.mark.parametrize("path", ["work-item-types/{type_id}/work-item-properties/", "work-item-properties/"])
def test_properties_are_listed_as_a_plain_list(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    dropdown: db_models.IssueProperty,
    path: str,
) -> None:
    response: api_response.Response = api_key_client.get(get_url(project, path.format(type_id=task.id)))

    assert (response.status_code, response.json()) == (200, [get_property_body(dropdown)])


def test_property_cannot_be_created_without_a_type(
    api_key_client: api_test.APIClient, project: db_models.Project
) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, "work-item-properties/"), {"display_name": "Loose", "property_type": "BOOLEAN"}, format="json"
    )

    assert response.status_code == 405, response.data


PROPERTY_PATHS: t.List[str] = ["work-item-types/{type_id}/work-item-properties/{id}/", "work-item-properties/{id}/"]


@pytest.mark.parametrize("path", PROPERTY_PATHS)
def test_property_is_retrieved(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    dropdown: db_models.IssueProperty,
    path: str,
) -> None:
    response: api_response.Response = api_key_client.get(get_url(project, path.format(type_id=task.id, id=dropdown.id)))

    assert (response.status_code, response.json()) == (200, get_property_body(dropdown))


@pytest.mark.parametrize("path", PROPERTY_PATHS)
def test_property_is_updated(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    dropdown: db_models.IssueProperty,
    path: str,
) -> None:
    response: api_response.Response = api_key_client.patch(
        get_url(project, path.format(type_id=task.id, id=dropdown.id)),
        {"display_name": "Labels", "is_required": True},
        format="json",
    )

    dropdown.refresh_from_db()
    assert (response.status_code, response.json(), dropdown.display_name, dropdown.is_required) == (
        200,
        get_property_body(dropdown),
        "Labels",
        True,
    )


@pytest.mark.parametrize("path", PROPERTY_PATHS)
def test_property_is_deleted(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    dropdown: db_models.IssueProperty,
    path: str,
) -> None:
    response: api_response.Response = api_key_client.delete(
        get_url(project, path.format(type_id=task.id, id=dropdown.id))
    )

    assert (response.status_code, db_models.IssueProperty.objects.count()) == (204, 0)


# workitem_property tool: options


def test_options_are_listed_as_a_plain_list(
    api_key_client: api_test.APIClient, project: db_models.Project, dropdown: db_models.IssueProperty
) -> None:
    response: api_response.Response = api_key_client.get(
        get_url(project, f"work-item-properties/{dropdown.id}/options/")
    )

    assert (response.status_code, response.json()) == (
        200,
        [get_option_body(option) for option in dropdown.options.all()],
    )


def test_option_is_created(
    api_key_client: api_test.APIClient, project: db_models.Project, dropdown: db_models.IssueProperty
) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-item-properties/{dropdown.id}/options/"),
        {"name": "Green", "is_default": True},
        format="json",
    )

    assert (response.status_code, response.json()) == (201, get_option_body(dropdown.options.get(name="Green")))


def test_option_is_created_under_the_parent_the_sdk_sends(
    api_key_client: api_test.APIClient, project: db_models.Project, location: db_models.IssueProperty
) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-item-properties/{location.id}/options/"),
        {"name": "Texas", "parent": str(location.options.get(name="USA").id)},
        format="json",
    )

    texas: db_models.IssuePropertyOption = location.options.get(name="Texas")
    assert (response.status_code, response.json(), texas.parent.name) == (201, get_option_body(texas), "USA")


def test_option_is_retrieved_with_the_number_of_work_items_that_use_it(
    api_key_client: api_test.APIClient, project: db_models.Project, dropdown: db_models.IssueProperty
) -> None:
    option: db_models.IssuePropertyOption = dropdown.options.get(name="Red")

    response: api_response.Response = api_key_client.get(
        get_url(project, f"work-item-properties/{dropdown.id}/options/{option.id}/")
    )

    assert (response.status_code, response.json()) == (200, {**get_option_body(option), "work_item_count": 0})


def test_option_is_updated(
    api_key_client: api_test.APIClient, project: db_models.Project, dropdown: db_models.IssueProperty
) -> None:
    option: db_models.IssuePropertyOption = dropdown.options.get(name="Red")

    response: api_response.Response = api_key_client.patch(
        get_url(project, f"work-item-properties/{dropdown.id}/options/{option.id}/"), {"name": "Crimson"}, format="json"
    )

    option.refresh_from_db()
    assert (response.status_code, response.json(), option.name) == (200, get_option_body(option), "Crimson")


def test_option_is_deleted(
    api_key_client: api_test.APIClient, project: db_models.Project, dropdown: db_models.IssueProperty
) -> None:
    option: db_models.IssuePropertyOption = dropdown.options.get(name="Red")

    response: api_response.Response = api_key_client.delete(
        get_url(project, f"work-item-properties/{dropdown.id}/options/{option.id}/")
    )

    assert (response.status_code, list(dropdown.options.values_list("name", flat=True))) == (204, ["Blue"])


def test_deleting_a_used_option_needs_no_confirmation(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    dropdown: db_models.IssueProperty,
) -> None:
    red: db_models.IssuePropertyOption = dropdown.options.get(name="Red")
    db_models.Issue.objects.filter(pk=issue.pk).update(custom_properties={str(dropdown.id): [str(red.id)]})

    response: api_response.Response = api_key_client.delete(
        get_url(project, f"work-item-properties/{dropdown.id}/options/{red.id}/")
    )

    issue.refresh_from_db()
    assert (response.status_code, issue.custom_properties, issue.description_html) == (
        204,
        {},
        "<p></p><p>Tags: Red</p>",
    )


# workitem_property tool: values


@pytest.mark.parametrize(
    ("property_fields", "supplied", "expected"),
    [
        ({"property_type": "TEXT", "settings": {"display_format": "single-line"}}, "007", "007"),
        ({"property_type": "DECIMAL"}, 7, 7),
        ({"property_type": "BOOLEAN"}, False, False),
        ({"property_type": "DATETIME"}, "2026-01-15", "2026-01-15"),
        ({"property_type": "URL"}, "https://plane.so", "https://plane.so"),
    ],
)
def test_value_is_set_and_read_back(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    property_fields: t.Dict[str, t.Any],
    supplied: t.Any,
    expected: t.Any,
) -> None:
    property: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project, issue_type=issue.type, display_name="Field", **property_fields
    )
    url: str = get_url(project, f"work-items/{issue.id}/work-item-properties/{property.id}/values/")

    written: api_response.Response = api_key_client.post(url, {"value": supplied}, format="json")
    read: api_response.Response = api_key_client.get(url)

    body: t.Dict[str, t.Any] = get_value_body(issue, property, expected)
    assert (written.status_code, written.json(), read.status_code, read.json()) == (200, body, 200, body)


@pytest.mark.parametrize("picked", [["Red", "Blue"], "Blue"])
def test_multi_value_is_a_list_of_details(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    dropdown: db_models.IssueProperty,
    picked: t.Union[str, t.List[str]],
) -> None:
    ids: t.Dict[str, str] = {option.name: str(option.id) for option in dropdown.options.all()}
    names: t.List[str] = picked if isinstance(picked, list) else [picked]

    response: api_response.Response = api_key_client.patch(
        get_url(project, f"work-items/{issue.id}/work-item-properties/{dropdown.id}/values/"),
        {"value": [ids[name] for name in names] if isinstance(picked, list) else ids[picked]},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        200,
        [get_value_body(issue, dropdown, ids[name]) for name in names],
    )


# /api/v1/ checks mandatory levels as little as mandatory properties, so the first level alone is stored.
@pytest.mark.parametrize("picked", [["USA", "California"], ["USA"]])
def test_cascading_value_is_a_list_of_details_from_the_first_level_down(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    location: db_models.IssueProperty,
    picked: t.List[str],
) -> None:
    ids: t.Dict[str, str] = {option.name: str(option.id) for option in location.options.all()}
    url: str = get_url(project, f"work-items/{issue.id}/work-item-properties/{location.id}/values/")

    written: api_response.Response = api_key_client.post(url, {"value": [ids[name] for name in picked]}, format="json")
    read: api_response.Response = api_key_client.get(url)

    body: t.List[t.Dict[str, t.Any]] = [get_value_body(issue, location, ids[name]) for name in picked]
    assert (written.status_code, written.json(), read.status_code, read.json()) == (200, body, 200, body)


def test_rich_text_value_is_an_object_in_and_a_detail_out(
    api_key_client: api_test.APIClient, project: db_models.Project, issue: db_models.Issue
) -> None:
    property: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project,
        issue_type=issue.type,
        display_name="Notes",
        property_type=PropertyType.RELATION,
        relation_type=RelationType.RICH_TEXT,
    )

    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{issue.id}/work-item-properties/{property.id}/values/"),
        {"value": {"description_html": "<p>Some <strong>notes</strong></p>"}},
        format="json",
    )

    issue.refresh_from_db()
    assert (response.status_code, response.json(), issue.custom_properties) == (
        200,
        {
            **get_value_body(issue, property, None),
            "value_detail": {
                "id": None,
                "description_html": "<p>Some <strong>notes</strong></p>",
                "description_stripped": "Some notes",
            },
        },
        {str(property.id): "<p>Some <strong>notes</strong></p>"},
    )


def test_rich_text_sent_as_a_string_gets_the_refusal_the_mcp_server_recognizes(
    api_key_client: api_test.APIClient, project: db_models.Project, issue: db_models.Issue
) -> None:
    property: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project,
        issue_type=issue.type,
        display_name="Notes",
        property_type=PropertyType.RELATION,
        relation_type=RelationType.RICH_TEXT,
    )

    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{issue.id}/work-item-properties/{property.id}/values/"),
        {"value": "<p>Notes</p>"},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"error": "Rich text value must be an object with description_html."},
    )


def test_unset_value_is_not_found(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    dropdown: db_models.IssueProperty,
) -> None:
    response: api_response.Response = api_key_client.get(
        get_url(project, f"work-items/{issue.id}/work-item-properties/{dropdown.id}/values/")
    )

    assert response.status_code == 404, response.data


def test_value_is_deleted(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    dropdown: db_models.IssueProperty,
) -> None:
    db_models.Issue.objects.filter(pk=issue.pk).update(
        custom_properties={str(dropdown.id): [str(dropdown.options.first().id)]}
    )

    response: api_response.Response = api_key_client.delete(
        get_url(project, f"work-items/{issue.id}/work-item-properties/{dropdown.id}/values/")
    )

    issue.refresh_from_db()
    assert (response.status_code, issue.custom_properties) == (204, {})


@pytest.fixture
def formula(project: db_models.Project, issue: db_models.Issue) -> db_models.IssueProperty:
    """The formula Shout of the work item's type, which reads its text property Code; the work item has "abc"."""
    code: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project,
        issue_type=issue.type,
        display_name="Code",
        property_type=PropertyType.TEXT,
        settings={"display_format": "single-line"},
    )
    db_models.Issue.objects.filter(pk=issue.pk).update(custom_properties={str(code.id): "abc"})
    return db_models.IssueProperty.objects.create(
        project=project,
        issue_type=issue.type,
        display_name="Shout",
        property_type=PropertyType.FORMULA,
        settings={"expression": "UPPER({{Code}})"},
    )


def test_formula_value_is_read(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    formula: db_models.IssueProperty,
) -> None:
    response: api_response.Response = api_key_client.get(
        get_url(project, f"work-items/{issue.id}/work-item-properties/{formula.id}/values/")
    )

    assert (response.status_code, response.json()) == (200, get_value_body(issue, formula, "ABC"))


def test_formula_value_is_not_written(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    formula: db_models.IssueProperty,
) -> None:
    response: api_response.Response = api_key_client.post(
        get_url(project, f"work-items/{issue.id}/work-item-properties/{formula.id}/values/"),
        {"value": "x"},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"custom_properties": {str(formula.id): ["This property is read-only."]}},
    )


@pytest.fixture
def inline_issue_activity() -> t.Iterator[None]:
    """No worker consumes the queue in tests, so the activity task runs inside the request."""
    with mock.patch.object(
        issue_activities_task.issue_activity, "delay", side_effect=issue_activities_task.issue_activity.run
    ):
        yield


@pytest.mark.usefixtures("inline_issue_activity")
def test_setting_a_value_records_activity(
    api_key_client: api_test.APIClient, project: db_models.Project, issue: db_models.Issue
) -> None:
    score: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project, issue_type=issue.type, display_name="Score", property_type=PropertyType.DECIMAL
    )
    db_models.Issue.objects.filter(pk=issue.pk).update(custom_properties={str(score.id): 1})

    api_key_client.post(
        get_url(project, f"work-items/{issue.id}/work-item-properties/{score.id}/values/"),
        {"value": 2},
        format="json",
    )

    assert list(
        db_models.IssueActivity.objects.filter(issue=issue).values_list(
            "field", "new_identifier", "old_value", "new_value", "comment"
        )
    ) == [("custom_property", score.id, "1", "2", "updated Score to ")]


# workitem tool


def test_work_item_is_created_without_the_values_the_sdk_cannot_send(
    api_key_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    db_models.IssueProperty.objects.create(
        project=project, issue_type=task, display_name="Score", property_type=PropertyType.DECIMAL, is_required=True
    )
    double: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project,
        issue_type=task,
        display_name="Double",
        property_type=PropertyType.FORMULA,
        settings={"expression": "{{Score}} * 2"},
    )

    response: api_response.Response = api_key_client.post(
        get_url(project, "work-items/"), {"name": "From an agent"}, format="json"
    )

    assert response.status_code == 201, response.data
    assert {
        key: response.json()[key] for key in ("type_id", "custom_properties", "formula_values", "formula_errors")
    } == {
        "type_id": str(task.id),
        "custom_properties": {},
        "formula_values": {str(double.id): None},
        "formula_errors": {},
    }


def test_work_item_type_is_changed_through_the_work_item(
    api_key_client: api_test.APIClient, project: db_models.Project, issue: db_models.Issue
) -> None:
    note: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project,
        issue_type=issue.type,
        display_name="Note",
        property_type=PropertyType.TEXT,
        settings={"display_format": "single-line"},
    )
    db_models.Issue.objects.filter(pk=issue.pk).update(custom_properties={str(note.id): "kept as text"})
    epic: db_models.IssueType = custom_properties.get_project_issue_types(project.id).get(name="Epic")

    response: api_response.Response = api_key_client.patch(
        get_url(project, f"work-items/{issue.id}/"), {"type_id": str(epic.id)}, format="json"
    )

    assert response.status_code == 200, response.data
    assert (response.json()["type_id"], response.json()["custom_properties"], response.json()["description_html"]) == (
        str(epic.id),
        {},
        "<p></p><p>Note: kept as text</p>",
    )


def test_null_type_leaves_the_type_alone(
    api_key_client: api_test.APIClient, project: db_models.Project, issue: db_models.Issue
) -> None:
    response: api_response.Response = api_key_client.patch(
        get_url(project, f"work-items/{issue.id}/"), {"type_id": None}, format="json"
    )

    assert (response.status_code, response.json()["type_id"]) == (200, str(issue.type_id))


@pytest.mark.usefixtures("inline_issue_activity")
def test_work_item_update_records_the_changed_values_as_activity(
    api_key_client: api_test.APIClient, project: db_models.Project, issue: db_models.Issue
) -> None:
    note: db_models.IssueProperty = db_models.IssueProperty.objects.create(
        project=project,
        issue_type=issue.type,
        display_name="Note",
        property_type=PropertyType.TEXT,
        settings={"display_format": "single-line"},
    )
    db_models.Issue.objects.filter(pk=issue.pk).update(custom_properties={str(note.id): "before"})

    api_key_client.patch(
        get_url(project, f"work-items/{issue.id}/"), {"custom_properties": {str(note.id): "after"}}, format="json"
    )

    assert list(
        db_models.IssueActivity.objects.filter(issue=issue).values_list(
            "field", "new_identifier", "old_value", "new_value", "comment"
        )
    ) == [("custom_property", note.id, "before", "after", "updated Note to ")]


def test_work_item_list_carries_formula_values(
    api_key_client: api_test.APIClient,
    project: db_models.Project,
    issue: db_models.Issue,
    formula: db_models.IssueProperty,
) -> None:
    response: api_response.Response = api_key_client.get(get_url(project, "work-items/"))

    assert [row["formula_values"] for row in response.json()["results"]] == [{str(formula.id): "ABC"}]
