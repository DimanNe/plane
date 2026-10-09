# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t
import unittest.mock as mock
import uuid

import pytest
import rest_framework.response as api_response
import rest_framework.test as api_test

import plane.bgtasks.issue_activities_task as issue_activities_task
import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties

pytestmark: t.List[pytest.MarkDecorator] = [pytest.mark.django_db, pytest.mark.contract]

PropertyType: t.TypeAlias = db_models.IssueProperty.PropertyType
RelationType: t.TypeAlias = db_models.IssueProperty.RelationType


def get_url(project: db_models.Project, path: str) -> str:
    return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/{path}"


def create_property(issue_type: db_models.IssueType, property_type: str, **fields: t.Any) -> db_models.IssueProperty:
    project: db_models.Project = db_models.ProjectIssueType.objects.get(issue_type=issue_type).project
    fields.setdefault("display_name", str(property_type))
    return db_models.IssueProperty.objects.create(
        project=project, issue_type=issue_type, property_type=property_type, **fields
    )


def create_options(
    property: db_models.IssueProperty, *names: str, parent: t.Optional[db_models.IssuePropertyOption] = None
) -> t.List[db_models.IssuePropertyOption]:
    return [
        db_models.IssuePropertyOption.objects.create(
            project=property.project, property=property, parent=parent, name=name
        )
        for name in names
    ]


def post_issue(
    client: api_test.APIClient, project: db_models.Project, data: t.Dict[str, t.Any]
) -> api_response.Response:
    return client.post(get_url(project, "issues/"), {"name": "Work item", **data}, format="json")


def create_issue(client: api_test.APIClient, project: db_models.Project, values: t.Dict[str, t.Any]) -> db_models.Issue:
    response: api_response.Response = post_issue(client, project, {"custom_properties": values})
    assert response.status_code == 201, response.data
    return db_models.Issue.objects.get(pk=response.data["id"])


def patch_issue(client: api_test.APIClient, issue: db_models.Issue, data: t.Dict[str, t.Any]) -> api_response.Response:
    return client.patch(get_url(issue.project, f"issues/{issue.id}/"), data, format="json")


def post_draft(
    client: api_test.APIClient, project: db_models.Project, data: t.Dict[str, t.Any]
) -> api_response.Response:
    return client.post(
        f"/api/workspaces/{project.workspace.slug}/draft-issues/",
        {"name": "Draft", "project_id": str(project.id), **data},
        format="json",
    )


@pytest.fixture
def plain_project(workspace: db_models.Workspace, create_user: db_models.User) -> db_models.Project:
    project: db_models.Project = db_models.Project.objects.create(workspace=workspace, name="Plain", identifier="PL")
    db_models.ProjectMember.objects.create(project=project, member=create_user, role=20)
    return project


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
def epic(project: db_models.Project) -> db_models.IssueType:
    return custom_properties.get_project_issue_types(project.id).get(name="Epic")


@pytest.fixture
def teammate(project: db_models.Project) -> db_models.User:
    user: db_models.User = db_models.User.objects.create(email="teammate@plane.so", username="teammate")
    db_models.WorkspaceMember.objects.create(workspace=project.workspace, member=user, role=15)
    db_models.ProjectMember.objects.create(project=project, member=user, role=15)
    return user


# Work item types


def test_enabling_types_creates_default_task_and_epic(
    session_client: api_test.APIClient, plain_project: db_models.Project
) -> None:
    response: api_response.Response = session_client.patch(
        f"/api/workspaces/{plain_project.workspace.slug}/projects/{plain_project.id}/",
        {"is_issue_type_enabled": True},
        format="json",
    )
    assert response.status_code == 200, response.data

    actual: t.List[t.Tuple[str, bool, bool, bool]] = [
        (item["name"], item["is_default"], item["is_active"], item["is_epic"])
        for item in session_client.get(get_url(plain_project, "work-item-types/")).data
    ]
    assert actual == [("Task", True, True, False), ("Epic", False, True, False)]


def test_enabling_types_gives_existing_work_items_the_default_type(
    session_client: api_test.APIClient, plain_project: db_models.Project
) -> None:
    issue: db_models.Issue = db_models.Issue.objects.create(project=plain_project, name="Existing")

    session_client.patch(
        f"/api/workspaces/{plain_project.workspace.slug}/projects/{plain_project.id}/",
        {"is_issue_type_enabled": True},
        format="json",
    )

    issue.refresh_from_db()
    assert issue.type == custom_properties.get_project_issue_types(plain_project.id).get(is_default=True)


def test_types_cannot_be_disabled_once_enabled(session_client: api_test.APIClient, project: db_models.Project) -> None:
    response: api_response.Response = session_client.patch(
        f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/",
        {"is_issue_type_enabled": False},
        format="json",
    )
    assert (response.status_code, response.data) == (
        400,
        {"is_issue_type_enabled": ["Work item types cannot be disabled once enabled."]},
    )


def test_updating_a_project_with_types_creates_no_more_types(
    session_client: api_test.APIClient, project: db_models.Project
) -> None:
    session_client.patch(
        f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/", {"name": "Renamed"}, format="json"
    )
    assert sorted(custom_properties.get_project_issue_types(project.id).values_list("name", flat=True)) == [
        "Epic",
        "Task",
    ]


def test_type_is_created_in_its_project_only(
    session_client: api_test.APIClient, project: db_models.Project, plain_project: db_models.Project
) -> None:
    response: api_response.Response = session_client.post(
        get_url(project, "work-item-types/"), {"name": "Bug", "description": "A defect"}, format="json"
    )
    assert response.status_code == 201, response.data
    assert list(
        custom_properties.get_project_issue_types(project.id).values_list("name", flat=True).order_by("name")
    ) == [
        "Bug",
        "Epic",
        "Task",
    ]
    assert not custom_properties.get_project_issue_types(plain_project.id).exists()


def test_type_needs_types_enabled(session_client: api_test.APIClient, plain_project: db_models.Project) -> None:
    response: api_response.Response = session_client.post(
        get_url(plain_project, "work-item-types/"), {"name": "Bug"}, format="json"
    )
    assert (response.status_code, response.data) == (
        400,
        {"error": "Work item types are not enabled for this project."},
    )


def test_type_name_is_unique_in_the_project(session_client: api_test.APIClient, project: db_models.Project) -> None:
    response: api_response.Response = session_client.post(
        get_url(project, "work-item-types/"), {"name": "task"}, format="json"
    )
    assert (response.status_code, response.data) == (
        400,
        {"name": ["The project already has a work item type with this name."]},
    )


def test_name_of_a_deleted_type_can_be_used_again(
    session_client: api_test.APIClient, project: db_models.Project
) -> None:
    created: api_response.Response = session_client.post(
        get_url(project, "work-item-types/"), {"name": "Bug"}, format="json"
    )
    session_client.delete(get_url(project, f"work-item-types/{created.data['id']}/"))

    response: api_response.Response = session_client.post(
        get_url(project, "work-item-types/"), {"name": "Bug"}, format="json"
    )
    assert response.status_code == 201, response.data


def test_making_a_type_the_default_replaces_the_previous_default(
    session_client: api_test.APIClient, project: db_models.Project, epic: db_models.IssueType
) -> None:
    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-types/{epic.id}/"), {"is_default": True}, format="json"
    )
    assert response.status_code == 200, response.data
    assert list(custom_properties.get_project_issue_types(project.id).filter(is_default=True)) == [epic]


@pytest.mark.parametrize(
    ("method", "data", "expected"),
    [
        ("patch", {"is_active": False}, {"is_active": ["The default type cannot be disabled."]}),
        ("patch", {"is_default": False}, {"is_default": ["Make another type the default instead."]}),
        ("delete", None, {"error": "The default type cannot be deleted."}),
    ],
)
def test_default_type_stays_active_default_and_present(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    method: str,
    data: t.Optional[t.Dict[str, bool]],
    expected: t.Dict[str, t.Any],
) -> None:
    response: api_response.Response = getattr(session_client, method)(
        get_url(project, f"work-item-types/{task.id}/"), data, format="json"
    )
    assert (response.status_code, response.data) == (400, expected)


def test_deleting_a_type_leaves_its_work_items_on_it(
    session_client: api_test.APIClient, project: db_models.Project, epic: db_models.IssueType
) -> None:
    response: api_response.Response = post_issue(session_client, project, {"type_id": str(epic.id)})

    assert session_client.delete(get_url(project, f"work-item-types/{epic.id}/")).status_code == 204

    assert db_models.Issue.objects.get(pk=response.data["id"]).type_id == epic.id
    assert list(custom_properties.get_project_issue_types(project.id).values_list("name", flat=True)) == ["Task"]


def test_inactive_type_refuses_new_work_items(
    session_client: api_test.APIClient, project: db_models.Project, epic: db_models.IssueType
) -> None:
    session_client.patch(get_url(project, f"work-item-types/{epic.id}/"), {"is_active": False}, format="json")

    response: api_response.Response = post_issue(session_client, project, {"type_id": str(epic.id)})
    assert (response.status_code, response.json()) == (
        400,
        {"type_id": ["Choose an active work item type of the project."]},
    )


def test_work_item_of_an_inactive_type_stays_editable(
    session_client: api_test.APIClient, project: db_models.Project, epic: db_models.IssueType
) -> None:
    field: db_models.IssueProperty = create_property(
        epic, PropertyType.TEXT, settings={"display_format": "single-line"}
    )
    issue: db_models.Issue = db_models.Issue.objects.get(
        pk=post_issue(session_client, project, {"type_id": str(epic.id)}).data["id"]
    )
    session_client.patch(get_url(project, f"work-item-types/{epic.id}/"), {"is_active": False}, format="json")

    response: api_response.Response = patch_issue(session_client, issue, {"custom_properties": {str(field.id): "x"}})
    assert response.status_code == 204, response.data
    issue.refresh_from_db()
    assert issue.custom_properties == {str(field.id): "x"}


def test_type_of_another_project_is_refused(
    session_client: api_test.APIClient, project: db_models.Project, plain_project: db_models.Project
) -> None:
    plain_project.is_issue_type_enabled = True
    plain_project.save()
    custom_properties.enable_project_types(plain_project)
    foreign: db_models.IssueType = custom_properties.get_project_issue_types(plain_project.id).get(name="Epic")

    response: api_response.Response = post_issue(session_client, project, {"type_id": str(foreign.id)})
    assert response.status_code == 400, response.data


def test_only_a_project_admin_changes_types(
    session_client: api_test.APIClient, project: db_models.Project, create_user: db_models.User
) -> None:
    db_models.ProjectMember.objects.filter(project=project, member=create_user).update(role=15)

    actual: t.Tuple[int, int] = (
        session_client.get(get_url(project, "work-item-types/")).status_code,
        session_client.post(get_url(project, "work-item-types/"), {"name": "Bug"}, format="json").status_code,
    )
    assert actual == (200, 403)


# Properties


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {"property_type": "TEXT", "settings": {"display_format": "multi-line"}},
            ("TEXT", None, {"display_format": "multi-line"}),
        ),
        (
            {"property_type": "TEXT", "settings": {"display_format": "readonly"}, "default_value": ["Fixed"]},
            ("TEXT", None, {"display_format": "readonly"}),
        ),
        ({"property_type": "DECIMAL", "default_value": ["2.5"]}, ("DECIMAL", None, {})),
        ({"property_type": "OPTION", "is_multi": True}, ("OPTION", None, {})),
        ({"property_type": "BOOLEAN"}, ("BOOLEAN", None, {})),
        (
            {"property_type": "DATETIME", "settings": {"display_format": "dd/MM/yyyy"}},
            ("DATETIME", None, {"display_format": "dd/MM/yyyy"}),
        ),
        ({"property_type": "RELATION", "relation_type": "USER"}, ("RELATION", "USER", {})),
        ({"property_type": "RELATION", "relation_type": "RICH_TEXT"}, ("RELATION", "RICH_TEXT", {})),
        ({"property_type": "URL", "relation_type": "USER"}, ("URL", None, {})),
        (
            {"property_type": "FORMULA", "settings": {"expression": "ROUND(7 / 2)"}},
            ("FORMULA", None, {"expression": "ROUND(7 / 2)"}),
        ),
        (
            {"property_type": "CASCADING"},
            (
                "CASCADING",
                None,
                {"levels": [{"name": "Level 1", "is_required": False}, {"name": "Level 2", "is_required": False}]},
            ),
        ),
        (
            {
                "property_type": "CASCADING",
                "settings": {"levels": [{"name": "Country", "is_required": True}, {"name": "State"}, {"name": "City"}]},
            },
            (
                "CASCADING",
                None,
                {
                    "levels": [
                        {"name": "Country", "is_required": True},
                        {"name": "State", "is_required": False},
                        {"name": "City", "is_required": False},
                    ]
                },
            ),
        ),
    ],
)
def test_property_of_each_type_is_created(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    data: t.Dict[str, t.Any],
    expected: t.Tuple[str, t.Optional[str], t.Dict[str, str]],
) -> None:
    response: api_response.Response = session_client.post(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/"),
        {"display_name": "Field", **data},
        format="json",
    )
    assert response.status_code == 201, response.data
    property: db_models.IssueProperty = db_models.IssueProperty.objects.get(pk=response.data["id"])
    assert (property.property_type, property.relation_type, property.settings) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {"property_type": "CASCADING", "settings": {"levels": [{"name": "Country"}]}},
            {"settings": {"levels": {"non_field_errors": ["Ensure this field has at least 2 elements."]}}},
        ),
        (
            {"property_type": "CASCADING", "settings": {"levels": [{"name": str(index)} for index in range(5)]}},
            {"settings": {"levels": {"non_field_errors": ["Ensure this field has no more than 4 elements."]}}},
        ),
        (
            {"property_type": "CASCADING", "settings": {"levels": [{"name": "Country"}, {"name": "x" * 101}]}},
            {"settings": {"levels": [{}, {"name": ["Ensure this field has no more than 100 characters."]}]}},
        ),
        ({"property_type": "CASCADING", "is_required": True}, {"is_required": ["This property cannot be mandatory."]}),
        ({"property_type": "RELATION"}, {"relation_type": ["Choose USER or RICH_TEXT."]}),
        (
            {"property_type": "RELATION", "relation_type": "RELEASE"},
            {"relation_type": ['"RELEASE" is not a valid choice.']},
        ),
        ({"property_type": "TEXT"}, {"settings": {"display_format": ["This field is required."]}}),
        (
            {"property_type": "DATETIME", "settings": {"display_format": "yy-M-d"}},
            {"settings": {"display_format": ['"yy-M-d" is not a valid choice.']}},
        ),
        (
            {"property_type": "FORMULA", "settings": {"expression": "1 +"}},
            {"settings": {"expression": ["Expression ended unexpectedly."]}},
        ),
        (
            {"property_type": "FORMULA", "settings": {"expression": "{{Missing}} + {{Existing}}"}},
            {"settings": {"expression": ["Unknown property: missing."]}},
        ),
        (
            {"property_type": "FORMULA", "settings": {"expression": "{{Priority}} & {{Existing link}}"}},
            {"settings": {"expression": ["Unknown property: existing_link, priority."]}},
        ),
        ({"property_type": "BOOLEAN", "is_required": True}, {"is_required": ["This property cannot be mandatory."]}),
        (
            {"property_type": "FORMULA", "settings": {"expression": "1"}, "is_required": True},
            {"is_required": ["This property cannot be mandatory."]},
        ),
        (
            {"property_type": "TEXT", "settings": {"display_format": "readonly"}, "is_required": True},
            {"is_required": ["This property cannot be mandatory."]},
        ),
        (
            {"property_type": "DECIMAL", "default_value": ["many"]},
            {"default_value": {"0": ["A valid number is required."]}},
        ),
        (
            {"property_type": "DECIMAL", "display_name": "existing"},
            {"display_name": ["The work item type already has a property with this name."]},
        ),
        (
            {"property_type": "RELATION", "relation_type": "USER", "default_value": ["not-a-user-id"]},
            {"default_value": ["Choose from the members of the project."]},
        ),
        (
            {"property_type": "RELATION", "relation_type": "USER", "default_value": [str(uuid.uuid4())]},
            {"default_value": ["Choose from the members of the project."]},
        ),
    ],
)
def test_invalid_property_is_refused(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    data: t.Dict[str, t.Any],
    expected: t.Dict[str, t.Any],
) -> None:
    create_property(task, PropertyType.DECIMAL, display_name="Existing")
    create_property(task, PropertyType.URL, display_name="Existing link")

    response: api_response.Response = session_client.post(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/"),
        {"display_name": "Field", **data},
        format="json",
    )
    assert (response.status_code, response.json()) == (400, expected)


@pytest.mark.parametrize(
    "data",
    [
        {"property_type": "URL"},
        {"relation_type": "RICH_TEXT"},
        {"is_multi": False},
    ],
)
def test_shape_of_stored_values_is_fixed_at_creation(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType, data: t.Dict[str, t.Any]
) -> None:
    property: db_models.IssueProperty = create_property(
        task, PropertyType.RELATION, relation_type=RelationType.USER, is_multi=True
    )

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-properties/{property.id}/"), data, format="json"
    )
    assert (response.status_code, list(response.data)) == (400, list(data))


@pytest.mark.parametrize("display_format", ["multi-line", "readonly"])
def test_format_of_a_text_property_is_fixed_at_creation(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType, display_format: str
) -> None:
    property: db_models.IssueProperty = create_property(
        task, PropertyType.TEXT, settings={"display_format": "single-line"}
    )

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-properties/{property.id}/"),
        {"settings": {"display_format": display_format}},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"settings": {"display_format": ["This cannot change after the property is created."]}},
    )


def test_text_property_is_updated_with_the_format_it_has(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(
        task, PropertyType.TEXT, settings={"display_format": "single-line"}
    )

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-properties/{property.id}/"),
        {"description": "Short", "settings": {"display_format": "single-line"}},
        format="json",
    )

    assert (response.status_code, response.data["description"]) == (200, "Short")


def test_property_is_renamed(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.BOOLEAN)

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/{property.id}/"),
        {"display_name": "Reviewed"},
        format="json",
    )

    property.refresh_from_db()
    assert (response.status_code, property.display_name) == (200, "Reviewed")


def test_property_is_switched_inactive(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.BOOLEAN)

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/{property.id}/"),
        {"is_active": False},
        format="json",
    )

    property.refresh_from_db()
    assert (response.status_code, property.is_active) == (200, False)


def test_properties_are_listed_in_the_order_they_were_added(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    name: str
    for name in ("Zeta", "Alpha", "Mid"):
        session_client.post(
            get_url(project, f"work-item-types/{task.id}/work-item-properties/"),
            {"display_name": name, "property_type": "BOOLEAN"},
            format="json",
        )

    response: api_response.Response = session_client.get(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/")
    )
    assert [item["display_name"] for item in response.data] == ["Zeta", "Alpha", "Mid"]


def test_property_is_moved_by_its_sort_order(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    first: db_models.IssueProperty = create_property(task, PropertyType.BOOLEAN, display_name="First")
    second: db_models.IssueProperty = create_property(task, PropertyType.BOOLEAN, display_name="Second")

    session_client.patch(
        get_url(project, f"work-item-properties/{second.id}/"), {"sort_order": first.sort_order - 1}, format="json"
    )

    response: api_response.Response = session_client.get(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/")
    )
    assert [item["display_name"] for item in response.data] == ["Second", "First"]


def test_project_list_has_the_properties_of_every_type(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType, epic: db_models.IssueType
) -> None:
    create_property(task, PropertyType.BOOLEAN, display_name="On task")
    create_property(epic, PropertyType.BOOLEAN, display_name="On epic")

    response: api_response.Response = session_client.get(get_url(project, "work-item-properties/"))
    assert sorted((item["display_name"], item["issue_type"]) for item in response.data) == [
        ("On epic", epic.id),
        ("On task", task.id),
    ]


def test_deleted_property_leaves_the_list(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.BOOLEAN)

    assert session_client.delete(get_url(project, f"work-item-properties/{property.id}/")).status_code == 204
    assert session_client.get(get_url(project, "work-item-properties/")).data == []


# Dropdown options


def test_dropdown_is_created_with_its_options(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    response: api_response.Response = session_client.post(
        get_url(project, f"work-item-types/{task.id}/work-item-properties/"),
        {
            "display_name": "Severity",
            "property_type": "OPTION",
            "options": [{"name": "Low"}, {"name": "High", "is_default": True}],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert [(option["name"], option["is_default"]) for option in response.data["options"]] == [
        ("Low", False),
        ("High", True),
    ]


def test_option_is_added_after_the_existing_ones(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.OPTION)
    create_options(property, "Low", "High")

    response: api_response.Response = session_client.post(
        get_url(project, f"work-item-properties/{property.id}/options/"), {"name": "Critical"}, format="json"
    )
    assert response.status_code == 201, response.data
    assert [
        option["name"]
        for option in session_client.get(get_url(project, f"work-item-properties/{property.id}/options/")).data
    ] == ["Low", "High", "Critical"]


def test_option_name_is_unique_in_the_property(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.OPTION)
    create_options(property, "Low")

    response: api_response.Response = session_client.post(
        get_url(project, f"work-item-properties/{property.id}/options/"), {"name": "low"}, format="json"
    )
    assert (response.status_code, response.data) == (
        400,
        {"name": ["The property already has an option with this name."]},
    )


def test_only_a_dropdown_takes_options(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.BOOLEAN)

    response: api_response.Response = session_client.post(
        get_url(project, f"work-item-properties/{property.id}/options/"), {"name": "Low"}, format="json"
    )
    assert response.status_code == 404, response.data


@pytest.mark.parametrize(("is_multi", "expected"), [(False, ["High"]), (True, ["Low", "High"])])
def test_single_select_dropdown_keeps_one_default_option(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    is_multi: bool,
    expected: t.List[str],
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.OPTION, is_multi=is_multi)
    low: db_models.IssuePropertyOption
    high: db_models.IssuePropertyOption
    low, high = create_options(property, "Low", "High")
    session_client.patch(
        get_url(project, f"work-item-properties/{property.id}/options/{low.id}/"), {"is_default": True}, format="json"
    )

    session_client.patch(
        get_url(project, f"work-item-properties/{property.id}/options/{high.id}/"), {"is_default": True}, format="json"
    )

    assert list(property.options.filter(is_default=True).values_list("name", flat=True)) == expected


def test_option_reports_how_many_work_items_use_it(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    single: db_models.IssueProperty = create_property(task, PropertyType.OPTION, display_name="Single")
    low: db_models.IssuePropertyOption
    high: db_models.IssuePropertyOption
    low, high = create_options(single, "Low", "High")
    create_issue(session_client, project, {str(single.id): str(low.id)})
    create_issue(session_client, project, {str(single.id): str(low.id)})
    create_issue(session_client, project, {str(single.id): str(high.id)})

    response: api_response.Response = session_client.get(
        get_url(project, f"work-item-properties/{single.id}/options/{low.id}/")
    )
    assert (response.status_code, response.data["work_item_count"]) == (200, 2)


@pytest.mark.parametrize(
    ("is_multi", "selected", "expected"),
    [
        (False, "Low", None),
        (True, ["Low"], None),
        (True, ["Low", "High"], ["High"]),
    ],
)
def test_deleting_a_used_option_moves_it_into_the_description(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    is_multi: bool,
    selected: t.Union[str, t.List[str]],
    expected: t.Optional[t.List[str]],
) -> None:
    property: db_models.IssueProperty = create_property(
        task, PropertyType.OPTION, display_name="Severity <1>", is_multi=is_multi
    )
    ids: t.Dict[str, str] = {option.name: str(option.id) for option in create_options(property, "Low", "High")}
    issue: db_models.Issue = db_models.Issue.objects.get(
        pk=post_issue(
            session_client,
            project,
            {
                "description_html": "<p>Before</p>",
                "custom_properties": {
                    str(property.id): [ids[name] for name in selected] if is_multi else ids[selected]
                },
            },
        ).data["id"]
    )

    response: api_response.Response = session_client.delete(
        get_url(project, f"work-item-properties/{property.id}/options/{ids['Low']}/")
    )

    assert response.status_code == 204, response.data
    issue.refresh_from_db()
    assert (issue.custom_properties.get(str(property.id)), issue.description_html, issue.description_stripped) == (
        expected and [ids[name] for name in expected],
        "<p>Before</p><p>Severity &lt;1&gt;: Low</p>",
        "BeforeSeverity <1>: Low",
    )


def test_deleting_an_option_leaves_other_work_items_alone(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.OPTION)
    low: db_models.IssuePropertyOption
    high: db_models.IssuePropertyOption
    low, high = create_options(property, "Low", "High")
    issue: db_models.Issue = create_issue(session_client, project, {str(property.id): str(high.id)})

    session_client.delete(get_url(project, f"work-item-properties/{property.id}/options/{low.id}/"))

    issue.refresh_from_db()
    assert (issue.custom_properties, issue.description_html) == ({str(property.id): str(high.id)}, "<p></p>")


def test_deleting_a_used_option_moves_it_into_the_description_of_a_draft(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.OPTION, display_name="Severity")
    low: db_models.IssuePropertyOption = create_options(property, "Low")[0]
    draft_id: str = post_draft(
        session_client,
        project,
        {"description_html": "<p>Before</p>", "custom_properties": {str(property.id): str(low.id)}},
    ).data["id"]

    session_client.delete(get_url(project, f"work-item-properties/{property.id}/options/{low.id}/"))

    draft: db_models.DraftIssue = db_models.DraftIssue.objects.get(pk=draft_id)
    assert (draft.custom_properties, draft.description_html) == ({}, "<p>Before</p><p>Severity: Low</p>")


# Values of a work item


@pytest.mark.parametrize(
    ("property_fields", "supplied", "expected"),
    [
        ({"property_type": "TEXT", "settings": {"display_format": "single-line"}}, " hello ", "hello"),
        ({"property_type": "TEXT", "settings": {"display_format": "multi-line"}}, "a\nb", "a\nb"),
        ({"property_type": "DECIMAL"}, 1.25, 1.25),
        ({"property_type": "DECIMAL"}, "7", 7),
        ({"property_type": "BOOLEAN"}, True, True),
        ({"property_type": "DATETIME"}, "2026-02-28", "2026-02-28"),
        ({"property_type": "URL"}, "https://example.com/a?b=1", "https://example.com/a?b=1"),
        (
            {"property_type": "RELATION", "relation_type": "RICH_TEXT"},
            "<p>Hello</p><script>alert(1)</script>",
            "<p>Hello</p>",
        ),
    ],
)
def test_value_is_stored_in_the_form_of_its_property_type(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    property_fields: t.Dict[str, t.Any],
    supplied: t.Any,
    expected: t.Any,
) -> None:
    property: db_models.IssueProperty = create_property(task, **property_fields)

    response: api_response.Response = post_issue(
        session_client, project, {"custom_properties": {str(property.id): supplied}}
    )

    assert (response.status_code, response.data.get("custom_properties")) == (201, {str(property.id): expected})


@pytest.mark.parametrize(
    ("property_fields", "supplied", "expected"),
    [
        ({"property_type": "TEXT"}, ["a"], ["Not a valid string."]),
        ({"property_type": "DECIMAL"}, "many", ["A valid number is required."]),
        ({"property_type": "DECIMAL"}, "nan", ["A valid number is required."]),
        ({"property_type": "BOOLEAN"}, "perhaps", ["Must be a valid boolean."]),
        (
            {"property_type": "DATETIME"},
            "2026-02-30",
            ["Date has wrong format. Use one of these formats instead: YYYY-MM-DD."],
        ),
        ({"property_type": "URL"}, "example", ["Enter a valid URL."]),
        (
            {"property_type": "RELATION", "relation_type": "RICH_TEXT"},
            {"description_html": "<p>x</p>"},
            ["Expected HTML text."],
        ),
        ({"property_type": "OPTION"}, str(uuid.uuid4()), ["Choose from the options of the property."]),
        ({"property_type": "OPTION"}, [str(uuid.uuid4()), str(uuid.uuid4())], ["Expected one selection."]),
        (
            {"property_type": "RELATION", "relation_type": "USER", "is_multi": True},
            [str(uuid.uuid4())],
            ["Choose from the members of the project."],
        ),
        ({"property_type": "FORMULA", "settings": {"expression": "1"}}, 2, ["This property is read-only."]),
        (
            {"property_type": "TEXT", "settings": {"display_format": "readonly"}, "default_value": ["Fixed"]},
            "Changed",
            ["This property is read-only."],
        ),
        (
            {"property_type": "TEXT", "is_active": False},
            "x",
            ["This is not an active property of the work item type."],
        ),
    ],
)
def test_invalid_value_is_refused(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    property_fields: t.Dict[str, t.Any],
    supplied: t.Any,
    expected: t.List[str],
) -> None:
    property: db_models.IssueProperty = create_property(task, **property_fields)

    response: api_response.Response = post_issue(
        session_client, project, {"custom_properties": {str(property.id): supplied}}
    )

    assert (response.status_code, response.json()) == (400, {"custom_properties": {str(property.id): expected}})


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        (["text"], {"custom_properties": ["Expected an object keyed by property id."]}),
        (
            {"not-a-property": 1},
            {"custom_properties": {"not-a-property": ["This is not an active property of the work item type."]}},
        ),
    ],
)
def test_values_are_an_object_keyed_by_property_id(
    session_client: api_test.APIClient, project: db_models.Project, supplied: t.Any, expected: t.Dict[str, t.Any]
) -> None:
    response: api_response.Response = post_issue(session_client, project, {"custom_properties": supplied})
    assert (response.status_code, response.json()) == (400, expected)


@pytest.mark.parametrize(("is_multi", "picked"), [(False, [0]), (True, [0, 1]), (True, [1])])
def test_dropdown_stores_the_ids_of_the_selected_options(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    is_multi: bool,
    picked: t.List[int],
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.OPTION, is_multi=is_multi)
    option_ids: t.List[str] = [str(option.id) for option in create_options(property, "Low", "High")]
    selected: t.List[str] = [option_ids[index] for index in picked]

    issue: db_models.Issue = create_issue(
        session_client, project, {str(property.id): selected if is_multi else selected[0]}
    )

    assert issue.custom_properties == {str(property.id): selected if is_multi else selected[0]}


def test_new_work_item_gets_the_default_values_of_its_type(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType, teammate: db_models.User
) -> None:
    number: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, default_value=["2.5"])
    owner: db_models.IssueProperty = create_property(
        task, PropertyType.RELATION, relation_type=RelationType.USER, default_value=[str(teammate.id)]
    )
    severity: db_models.IssueProperty = create_property(task, PropertyType.OPTION)
    high: db_models.IssuePropertyOption = create_options(severity, "Low", "High")[1]
    high.is_default = True
    high.save()
    create_property(task, PropertyType.TEXT, settings={"display_format": "single-line"})

    issue: db_models.Issue = create_issue(session_client, project, {})

    assert issue.custom_properties == {
        str(number.id): 2.5,
        str(owner.id): str(teammate.id),
        str(severity.id): str(high.id),
    }


@pytest.mark.parametrize(
    "property_fields",
    [
        {"property_type": "BOOLEAN"},
        {"property_type": "DECIMAL", "default_value": ["1"], "is_active": False},
    ],
)
def test_new_work_item_stores_nothing_for_a_checkbox_or_an_inactive_property(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    property_fields: t.Dict[str, t.Any],
) -> None:
    create_property(task, **property_fields)

    issue: db_models.Issue = create_issue(session_client, project, {})

    assert issue.custom_properties == {}


def test_mandatory_property_must_be_filled_to_create_a_work_item(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(
        task, PropertyType.DECIMAL, display_name="Score", is_required=True
    )

    response: api_response.Response = post_issue(session_client, project, {})

    assert (response.status_code, response.json(), db_models.Issue.objects.count()) == (
        400,
        {"custom_properties": {str(property.id): ["Score is mandatory."]}},
        0,
    )


def test_zero_fills_a_mandatory_property(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    property: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, is_required=True)

    assert post_issue(session_client, project, {"custom_properties": {str(property.id): 0}}).status_code == 201


def test_intake_work_item_is_created_without_mandatory_values(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    create_property(task, PropertyType.DECIMAL, is_required=True)
    db_models.Intake.objects.create(project=project, name="Intake", is_default=True)

    response: api_response.Response = session_client.post(
        get_url(project, "intake-issues/"), {"issue": {"name": "From intake"}}, format="json"
    )

    assert (response.status_code, list(db_models.Issue.objects.values_list("name", "type_id"))) == (
        200,
        [("From intake", task.id)],
    )


def test_mandatory_property_added_later_does_not_block_other_edits(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    issue: db_models.Issue = create_issue(session_client, project, {})
    create_property(task, PropertyType.DECIMAL, is_required=True)

    response: api_response.Response = patch_issue(session_client, issue, {"priority": "high"})

    assert response.status_code == 204, response.data
    issue.refresh_from_db()
    assert issue.priority == "high"


def test_value_is_written_while_another_mandatory_property_is_empty(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    issue: db_models.Issue = create_issue(session_client, project, {})
    note: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Note")
    create_property(task, PropertyType.DECIMAL, display_name="Score", is_required=True)

    response: api_response.Response = patch_issue(session_client, issue, {"custom_properties": {str(note.id): "x"}})

    issue.refresh_from_db()
    assert (response.status_code, issue.custom_properties) == (204, {str(note.id): "x"})


@pytest.mark.parametrize("empty", [None, "", []])
def test_mandatory_property_cannot_be_cleared(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType, empty: t.Any
) -> None:
    score: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, display_name="Score", is_required=True)
    issue: db_models.Issue = create_issue(session_client, project, {str(score.id): 5})

    response: api_response.Response = patch_issue(session_client, issue, {"custom_properties": {str(score.id): empty}})

    issue.refresh_from_db()
    assert (response.status_code, response.json(), issue.custom_properties) == (
        400,
        {"custom_properties": {str(score.id): ["Score is mandatory."]}},
        {str(score.id): 5},
    )


def test_update_writes_the_supplied_values_over_the_stored_ones(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    kept: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Kept")
    changed: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, display_name="Changed")
    cleared: db_models.IssueProperty = create_property(task, PropertyType.URL, display_name="Cleared")
    issue: db_models.Issue = create_issue(
        session_client, project, {str(kept.id): "old", str(changed.id): 1, str(cleared.id): "https://plane.so"}
    )

    response: api_response.Response = patch_issue(
        session_client, issue, {"custom_properties": {str(changed.id): 2, str(cleared.id): None}}
    )

    assert response.status_code == 204, response.data
    issue.refresh_from_db()
    assert issue.custom_properties == {str(kept.id): "old", str(changed.id): 2}


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ({}, (204, None)),
        ([], (400, {"custom_properties": ["Expected an object keyed by property id."]})),
    ],
)
def test_update_that_supplies_no_value_keeps_the_stored_ones(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    supplied: t.Any,
    expected: t.Tuple[int, t.Optional[t.Dict[str, t.List[str]]]],
) -> None:
    note: db_models.IssueProperty = create_property(task, PropertyType.TEXT)
    issue: db_models.Issue = create_issue(session_client, project, {str(note.id): "kept"})

    response: api_response.Response = patch_issue(session_client, issue, {"custom_properties": supplied})

    issue.refresh_from_db()
    assert ((response.status_code, response.data), issue.custom_properties) == (expected, {str(note.id): "kept"})


def test_update_does_not_write_back_values_it_read_before_another_writer(
    project: db_models.Project, task: db_models.IssueType
) -> None:
    first: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="First")
    second: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Second")
    issue: db_models.Issue = db_models.Issue.objects.create(project=project, name="Shared", type=task)
    stale: db_models.Issue = db_models.Issue.objects.get(pk=issue.pk)
    db_models.Issue.objects.filter(pk=issue.pk).update(custom_properties={str(first.id): "theirs"})

    changes: t.Dict[str, t.Any] = custom_properties.get_changes_for_update(
        stale, None, {str(second.id): "mine"}, None, check_required=True
    )

    assert changes == {"custom_properties": {str(first.id): "theirs", str(second.id): "mine"}}


def test_null_type_leaves_the_type_and_the_values_alone(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    note: db_models.IssueProperty = create_property(task, PropertyType.TEXT)
    issue: db_models.Issue = create_issue(session_client, project, {str(note.id): "kept"})

    response: api_response.Response = patch_issue(session_client, issue, {"type_id": None})

    issue.refresh_from_db()
    assert (response.status_code, issue.type_id, issue.custom_properties) == (204, task.id, {str(note.id): "kept"})


def test_changing_the_type_moves_the_values_into_the_description(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    epic: db_models.IssueType,
    create_user: db_models.User,
) -> None:
    text: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Note")
    score: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, display_name="Score")
    create_property(task, PropertyType.BOOLEAN, display_name="Reviewed")
    owner: db_models.IssueProperty = create_property(
        task, PropertyType.RELATION, relation_type=RelationType.USER, display_name="Owner"
    )
    rich: db_models.IssueProperty = create_property(
        task, PropertyType.RELATION, relation_type=RelationType.RICH_TEXT, display_name="Details"
    )
    points: db_models.IssueProperty = create_property(epic, PropertyType.DECIMAL, default_value=["2.5"])
    issue: db_models.Issue = db_models.Issue.objects.get(
        pk=post_issue(
            session_client,
            project,
            {
                "description_html": "<p>Before</p>",
                "custom_properties": {
                    str(text.id): "a < b",
                    str(score.id): 3,
                    str(owner.id): str(create_user.id),
                    str(rich.id): "<p><strong>Bold</strong></p>",
                },
            },
        ).data["id"]
    )

    response: api_response.Response = patch_issue(session_client, issue, {"type_id": str(epic.id)})

    assert response.status_code == 204, response.data
    issue.refresh_from_db()
    assert (issue.type_id, issue.custom_properties, issue.description_html) == (
        epic.id,
        {str(points.id): 2.5},
        "<p>Before</p><p>Note: a &lt; b</p><p>Score: 3</p>"
        f"<p>Owner: {create_user.display_name}</p><p>Details:</p><p><strong>Bold</strong></p>",
    )


def test_changing_the_type_needs_the_mandatory_values_of_the_new_type(
    session_client: api_test.APIClient, project: db_models.Project, epic: db_models.IssueType
) -> None:
    score: db_models.IssueProperty = create_property(epic, PropertyType.DECIMAL, display_name="Score", is_required=True)
    issue: db_models.Issue = create_issue(session_client, project, {})

    response: api_response.Response = patch_issue(session_client, issue, {"type_id": str(epic.id)})

    assert (response.status_code, response.json()) == (
        400,
        {"custom_properties": {str(score.id): ["Score is mandatory."]}},
    )


def test_member_picker_makes_the_selected_members_follow_the_work_item(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType, teammate: db_models.User
) -> None:
    property: db_models.IssueProperty = create_property(
        task, PropertyType.RELATION, relation_type=RelationType.USER, is_multi=True
    )

    issue: db_models.Issue = create_issue(session_client, project, {str(property.id): [str(teammate.id)]})

    assert list(db_models.IssueSubscriber.objects.filter(issue=issue).values_list("subscriber_id", flat=True)) == [
        teammate.id
    ]


def test_changing_the_type_makes_the_members_selected_on_the_new_type_follow(
    session_client: api_test.APIClient, project: db_models.Project, epic: db_models.IssueType, teammate: db_models.User
) -> None:
    create_property(epic, PropertyType.RELATION, relation_type=RelationType.USER, default_value=[str(teammate.id)])
    issue: db_models.Issue = create_issue(session_client, project, {})

    patch_issue(session_client, issue, {"type_id": str(epic.id)})

    assert list(db_models.IssueSubscriber.objects.filter(issue=issue).values_list("subscriber_id", flat=True)) == [
        teammate.id
    ]


def test_member_who_stopped_following_is_not_subscribed_again_by_a_later_save(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType, teammate: db_models.User
) -> None:
    picker: db_models.IssueProperty = create_property(
        task, PropertyType.RELATION, relation_type=RelationType.USER, display_name="Owner"
    )
    note: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Note")
    issue: db_models.Issue = create_issue(session_client, project, {str(picker.id): str(teammate.id)})
    db_models.IssueSubscriber.objects.filter(issue=issue).delete()

    patch_issue(session_client, issue, {"custom_properties": {str(note.id): "x"}})

    assert not db_models.IssueSubscriber.objects.filter(issue=issue).exists()


# Activity


@pytest.fixture
def inline_issue_activity() -> t.Iterator[None]:
    """No worker consumes the queue in tests, so the activity task runs inside the request."""
    with mock.patch.object(
        issue_activities_task.issue_activity, "delay", side_effect=issue_activities_task.issue_activity.run
    ):
        yield


@pytest.mark.usefixtures("inline_issue_activity")
def test_update_records_the_changed_values_as_activity(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    severity: db_models.IssueProperty = create_property(task, PropertyType.OPTION, display_name="Severity")
    low: db_models.IssuePropertyOption
    high: db_models.IssuePropertyOption
    low, high = create_options(severity, "Low", "High")
    note: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Note")
    score: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, display_name="Score")
    issue: db_models.Issue = create_issue(
        session_client, project, {str(severity.id): str(low.id), str(note.id): "same"}
    )

    patch_issue(
        session_client,
        issue,
        {"custom_properties": {str(severity.id): str(high.id), str(note.id): "same", str(score.id): "7"}},
    )

    assert sorted(
        db_models.IssueActivity.objects.filter(issue=issue, field="custom_property").values_list(
            "new_identifier", "old_value", "new_value", "comment"
        )
    ) == sorted(
        [
            (severity.id, "Low", "High", "updated Severity to "),
            (score.id, None, "7", "updated Score to "),
        ]
    )


@pytest.mark.usefixtures("inline_issue_activity")
def test_update_records_a_change_of_type_as_activity(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType, epic: db_models.IssueType
) -> None:
    issue: db_models.Issue = create_issue(session_client, project, {})

    patch_issue(session_client, issue, {"type_id": str(epic.id)})

    assert list(
        db_models.IssueActivity.objects.filter(issue=issue, field="type").values_list(
            "old_identifier", "new_identifier", "old_value", "new_value", "comment"
        )
    ) == [(task.id, epic.id, "Task", "Epic", "updated the type to ")]


# Cascading properties


def get_levels(*is_required: bool) -> t.Dict[str, t.List[t.Dict[str, t.Any]]]:
    names: t.Tuple[str, ...] = ("Country", "State", "City")
    return {"levels": [{"name": name, "is_required": flag} for name, flag in zip(names, is_required)]}


@pytest.fixture
def location(task: db_models.IssueType) -> db_models.IssueProperty:
    return create_property(
        task, PropertyType.CASCADING, display_name="Location", settings=get_levels(False, False, False)
    )


@pytest.fixture
def places(location: db_models.IssueProperty) -> t.Dict[str, str]:
    """Option name -> id. USA has California, with Los Angeles under it, and Texas; Canada has no options under it."""
    usa: db_models.IssuePropertyOption
    canada: db_models.IssuePropertyOption
    usa, canada = create_options(location, "USA", "Canada")
    california: db_models.IssuePropertyOption
    texas: db_models.IssuePropertyOption
    california, texas = create_options(location, "California", "Texas", parent=usa)
    los_angeles: db_models.IssuePropertyOption = create_options(location, "Los Angeles", parent=california)[0]
    return {option.name: str(option.id) for option in (usa, canada, california, texas, los_angeles)}


def test_mandatory_level_makes_the_levels_above_it_mandatory(
    session_client: api_test.APIClient, project: db_models.Project, location: db_models.IssueProperty
) -> None:
    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-properties/{location.id}/"),
        {"settings": get_levels(False, True, False)},
        format="json",
    )

    assert (response.status_code, response.data["settings"]) == (200, get_levels(True, True, False))


def test_option_is_created_under_an_option_of_the_level_above(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
) -> None:
    response: api_response.Response = session_client.post(
        get_url(project, f"work-item-properties/{location.id}/options/"),
        {"name": "Ontario", "parent": places["Canada"], "sub_level_label": "Town"},
        format="json",
    )

    assert response.status_code == 201, response.data
    assert (str(response.data["parent"]), response.data["sub_level_label"]) == (places["Canada"], "Town")


@pytest.mark.parametrize(
    ("parent", "name", "expected"),
    [
        ("USA", "texas", (400, {"name": ["The property already has an option with this name."]})),
        (None, "usa", (400, {"name": ["The property already has an option with this name."]})),
        ("Canada", "Texas", (201, None)),
        (None, "Texas", (201, None)),
        # Los Angeles is on the last level
        (
            "Los Angeles",
            "Downtown",
            (400, {"parent": ["Choose an option of the property that is above its last level."]}),
        ),
        ("Low", "Lower", (400, {"parent": ["Choose an option of the property."]})),
    ],
)
def test_option_needs_a_parent_above_the_last_level_and_a_name_no_other_option_under_it_has(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
    parent: t.Optional[str],
    name: str,
    expected: t.Tuple[int, t.Optional[t.Dict[str, t.List[str]]]],
) -> None:
    low: db_models.IssuePropertyOption = create_options(create_property(task, PropertyType.OPTION), "Low")[0]
    parent_ids: t.Dict[t.Optional[str], t.Optional[str]] = {**places, "Low": str(low.id), None: None}

    response: api_response.Response = session_client.post(
        get_url(project, f"work-item-properties/{location.id}/options/"),
        {"name": name, "parent": parent_ids[parent]},
        format="json",
    )

    assert (response.status_code, None if response.status_code == 201 else response.json()) == expected


def test_moving_an_option_moves_it_out_of_the_work_items_as_deleting_it_does(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
) -> None:
    issue: db_models.Issue = create_issue(
        session_client, project, {str(location.id): [places["USA"], places["California"], places["Los Angeles"]]}
    )

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-properties/{location.id}/options/{places['California']}/"),
        {"parent": places["Canada"]},
        format="json",
    )

    issue.refresh_from_db()
    assert (response.status_code, str(response.data["parent"]), issue.custom_properties, issue.description_html) == (
        200,
        places["Canada"],
        {str(location.id): [places["USA"]]},
        "<p></p><p>Location: California / Los Angeles</p>",
    )


@pytest.mark.parametrize(
    ("moved", "parent", "expected"),
    [
        ("California", None, "An option moves only to another option of the level above it."),
        ("California", "Los Angeles", "An option moves only to another option of the level above it."),
        ("Los Angeles", "Canada", "An option moves only to another option of the level above it."),
        ("USA", "Canada", "An option moves only to another option of the level above it."),
        ("California", "Low", "Choose an option of the property."),
    ],
)
def test_option_moves_only_to_another_option_of_the_level_above_it(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
    moved: str,
    parent: t.Optional[str],
    expected: str,
) -> None:
    low: db_models.IssuePropertyOption = create_options(create_property(task, PropertyType.OPTION), "Low")[0]
    parent_ids: t.Dict[t.Optional[str], t.Optional[str]] = {**places, "Low": str(low.id), None: None}

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-properties/{location.id}/options/{places[moved]}/"),
        {"parent": parent_ids[parent]},
        format="json",
    )

    assert (response.status_code, response.json()) == (400, {"parent": [expected]})


def test_moved_option_needs_a_name_no_option_under_its_new_parent_has(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
) -> None:
    create_options(location, "California", parent=location.options.get(name="Canada"))

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-properties/{location.id}/options/{places['California']}/"),
        {"parent": places["Canada"]},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"name": ["The property already has an option with this name."]},
    )


def test_deleting_an_option_deletes_the_options_under_it(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
) -> None:
    response: api_response.Response = session_client.delete(
        get_url(project, f"work-item-properties/{location.id}/options/{places['USA']}/")
    )

    assert (response.status_code, list(location.options.values_list("name", flat=True))) == (204, ["Canada"])


@pytest.mark.parametrize(
    ("deleted", "expected"),
    [
        ("USA", (None, "<p>Before</p><p>Location: USA / California / Los Angeles</p>")),
        ("California", (["USA"], "<p>Before</p><p>Location: California / Los Angeles</p>")),
        ("Los Angeles", (["USA", "California"], "<p>Before</p><p>Location: Los Angeles</p>")),
        ("Texas", (["USA", "California", "Los Angeles"], "<p>Before</p>")),
    ],
)
def test_deleting_a_chosen_option_moves_it_and_the_options_chosen_under_it_into_the_description(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
    deleted: str,
    expected: t.Tuple[t.Optional[t.List[str]], str],
) -> None:
    selected: t.List[str] = [places["USA"], places["California"], places["Los Angeles"]]
    issue: db_models.Issue = db_models.Issue.objects.get(
        pk=post_issue(
            session_client,
            project,
            {"description_html": "<p>Before</p>", "custom_properties": {str(location.id): selected}},
        ).data["id"]
    )

    session_client.delete(get_url(project, f"work-item-properties/{location.id}/options/{places[deleted]}/"))

    issue.refresh_from_db()
    assert (issue.custom_properties.get(str(location.id)), issue.description_html) == (
        expected[0] and [places[name] for name in expected[0]],
        expected[1],
    )


def test_deleting_a_level_deletes_its_options_and_moves_them_out_of_the_work_items(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
) -> None:
    issue: db_models.Issue = create_issue(
        session_client, project, {str(location.id): [places["USA"], places["California"], places["Los Angeles"]]}
    )

    response: api_response.Response = session_client.patch(
        get_url(project, f"work-item-properties/{location.id}/"),
        {"settings": {"levels": [{"name": "Country"}, {"name": "Region"}]}},
        format="json",
    )

    issue.refresh_from_db()
    assert (
        response.status_code,
        sorted(option["name"] for option in response.data["options"]),
        issue.custom_properties,
        issue.description_html,
    ) == (
        200,
        ["California", "Canada", "Texas", "USA"],
        {str(location.id): [places["USA"], places["California"]]},
        "<p></p><p>Location: Los Angeles</p>",
    )


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        (["USA"], ["USA"]),
        ("USA", ["USA"]),
        (["USA", "Texas"], ["USA", "Texas"]),
        (["USA", "California", "Los Angeles"], ["USA", "California", "Los Angeles"]),
    ],
)
def test_cascading_value_is_the_options_chosen_from_the_first_level_down(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
    supplied: t.Union[str, t.List[str]],
    expected: t.List[str],
) -> None:
    issue: db_models.Issue = create_issue(
        session_client,
        project,
        {str(location.id): places[supplied] if isinstance(supplied, str) else [places[name] for name in supplied]},
    )

    assert issue.custom_properties == {str(location.id): [places[name] for name in expected]}


@pytest.mark.parametrize(
    "supplied",
    [
        ["California"],
        ["USA", "Los Angeles"],
        ["Canada", "California"],
        ["California", "USA"],
        ["USA", "Unknown"],
    ],
)
def test_cascading_value_with_an_option_that_is_not_under_the_one_before_is_refused(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
    supplied: t.List[str],
) -> None:
    option_ids: t.Dict[str, str] = {**places, "Unknown": str(uuid.uuid4())}

    response: api_response.Response = post_issue(
        session_client, project, {"custom_properties": {str(location.id): [option_ids[name] for name in supplied]}}
    )

    assert (response.status_code, response.json()) == (
        400,
        {
            "custom_properties": {
                str(location.id): ["Choose one option for each level from the first, each under the one before."]
            }
        },
    )


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ([], "Country is mandatory."),
        (["USA"], "State is mandatory."),
        # Canada has no options under it
        (["Canada"], None),
        # City is not mandatory
        (["USA", "California"], None),
    ],
)
def test_mandatory_level_needs_an_option_when_the_option_above_it_has_options_under_it(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
    supplied: t.List[str],
    expected: t.Optional[str],
) -> None:
    db_models.IssueProperty.objects.filter(pk=location.pk).update(settings=get_levels(True, True, False))

    response: api_response.Response = post_issue(
        session_client, project, {"custom_properties": {str(location.id): [places[name] for name in supplied]}}
    )

    assert (response.status_code, response.json().get("custom_properties")) == (
        (400, {str(location.id): [expected]})
        if expected
        else (201, {str(location.id): [places[name] for name in supplied]})
    )


def test_draft_becomes_a_work_item_though_a_mandatory_level_is_empty(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
) -> None:
    db_models.IssueProperty.objects.filter(pk=location.pk).update(settings=get_levels(True, False, False))
    note: db_models.IssueProperty = create_property(task, PropertyType.TEXT, is_required=True)
    draft_id: str = post_draft(session_client, project, {}).data["id"]
    url: str = f"/api/workspaces/{project.workspace.slug}/draft-to-issue/{draft_id}/"

    without_note: api_response.Response = session_client.post(url, {"name": "Work item"}, format="json")
    with_note: api_response.Response = session_client.post(
        url, {"name": "Work item", "custom_properties": {str(note.id): "x"}}, format="json"
    )

    assert (without_note.status_code, without_note.json().get("custom_properties"), with_note.status_code) == (
        400,
        {str(note.id): [f"{note.display_name} is mandatory."]},
        201,
    )


def test_mandatory_level_of_a_property_without_options_needs_no_option(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    create_property(task, PropertyType.CASCADING, settings=get_levels(True, True))

    assert post_issue(session_client, project, {}).status_code == 201


def test_selection_that_leaves_a_mandatory_level_empty_is_not_saved(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
) -> None:
    issue: db_models.Issue = create_issue(session_client, project, {str(location.id): [places["Canada"]]})
    db_models.IssueProperty.objects.filter(pk=location.pk).update(settings=get_levels(True, True, False))

    response: api_response.Response = patch_issue(
        session_client, issue, {"custom_properties": {str(location.id): [places["USA"]]}}
    )

    issue.refresh_from_db()
    assert (response.status_code, response.json(), issue.custom_properties) == (
        400,
        {"custom_properties": {str(location.id): ["State is mandatory."]}},
        {str(location.id): [places["Canada"]]},
    )


@pytest.mark.usefixtures("inline_issue_activity")
def test_update_records_a_cascading_value_as_the_chosen_path(
    session_client: api_test.APIClient,
    project: db_models.Project,
    location: db_models.IssueProperty,
    places: t.Dict[str, str],
) -> None:
    issue: db_models.Issue = create_issue(session_client, project, {str(location.id): [places["Canada"]]})

    patch_issue(session_client, issue, {"custom_properties": {str(location.id): [places["USA"], places["California"]]}})

    assert list(
        db_models.IssueActivity.objects.filter(issue=issue, field="custom_property").values_list(
            "old_value", "new_value"
        )
    ) == [("Canada", "USA / California")]


# Formulas


@pytest.fixture
def scored_issue(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> t.Tuple[db_models.Issue, db_models.IssueProperty, db_models.IssueProperty]:
    points: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, display_name="Story Points")
    formula: db_models.IssueProperty = create_property(
        task, PropertyType.FORMULA, display_name="Cost", settings={"expression": "100 / {{story_points}}"}
    )
    return create_issue(session_client, project, {str(points.id): 4}), points, formula


def test_work_item_carries_the_value_of_its_formula(
    session_client: api_test.APIClient,
    scored_issue: t.Tuple[db_models.Issue, db_models.IssueProperty, db_models.IssueProperty],
) -> None:
    issue: db_models.Issue
    formula: db_models.IssueProperty
    issue, _, formula = scored_issue

    response: api_response.Response = session_client.get(get_url(issue.project, f"issues/{issue.id}/"))

    assert (response.data["formula_values"], response.data["formula_errors"]) == ({str(formula.id): 25.0}, {})


@pytest.mark.parametrize(("supplied", "expected"), [(3, "3 pts"), ("3.0", "3 pts"), (2.5, "2.5 pts")])
def test_formula_reads_a_whole_number_without_a_decimal_point(
    session_client: api_test.APIClient,
    project: db_models.Project,
    task: db_models.IssueType,
    supplied: t.Union[int, float, str],
    expected: str,
) -> None:
    points: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, display_name="Points")
    formula: db_models.IssueProperty = create_property(
        task, PropertyType.FORMULA, display_name="Label", settings={"expression": '{{Points}} & " pts"'}
    )
    issue: db_models.Issue = create_issue(session_client, project, {str(points.id): supplied})

    response: api_response.Response = session_client.get(get_url(project, f"issues/{issue.id}/"))

    assert response.data["formula_values"] == {str(formula.id): expected}


def test_failing_formula_reports_its_error(
    session_client: api_test.APIClient,
    scored_issue: t.Tuple[db_models.Issue, db_models.IssueProperty, db_models.IssueProperty],
) -> None:
    issue: db_models.Issue
    points: db_models.IssueProperty
    formula: db_models.IssueProperty
    issue, points, formula = scored_issue
    patch_issue(session_client, issue, {"custom_properties": {str(points.id): 0}})

    response: api_response.Response = session_client.get(get_url(issue.project, f"issues/{issue.id}/"))

    assert (response.data["formula_values"], response.data["formula_errors"]) == (
        {str(formula.id): None},
        {str(formula.id): "Division by zero."},
    )


def test_formula_reports_a_source_that_was_renamed(
    session_client: api_test.APIClient,
    scored_issue: t.Tuple[db_models.Issue, db_models.IssueProperty, db_models.IssueProperty],
) -> None:
    issue: db_models.Issue
    points: db_models.IssueProperty
    formula: db_models.IssueProperty
    issue, points, formula = scored_issue
    session_client.patch(
        get_url(issue.project, f"work-item-properties/{points.id}/"), {"display_name": "Estimate"}, format="json"
    )

    response: api_response.Response = session_client.get(get_url(issue.project, f"issues/{issue.id}/"))

    assert response.data["formula_errors"] == {str(formula.id): "Unknown property: story_points."}


def test_formula_with_a_renamed_source_can_still_be_switched_inactive(
    session_client: api_test.APIClient,
    scored_issue: t.Tuple[db_models.Issue, db_models.IssueProperty, db_models.IssueProperty],
) -> None:
    issue: db_models.Issue
    points: db_models.IssueProperty
    formula: db_models.IssueProperty
    issue, points, formula = scored_issue
    db_models.IssueProperty.objects.filter(pk=points.pk).update(display_name="Estimate")

    response: api_response.Response = session_client.patch(
        get_url(issue.project, f"work-item-properties/{formula.id}/"), {"is_active": False}, format="json"
    )

    assert (response.status_code, response.data["is_active"]) == (200, False)


@pytest.mark.parametrize("path", ["issues/", "issues/?group_by=priority", "issues/list/?issues={issue_id}"])
def test_list_rows_carry_type_values_and_formulas(
    session_client: api_test.APIClient,
    scored_issue: t.Tuple[db_models.Issue, db_models.IssueProperty, db_models.IssueProperty],
    path: str,
) -> None:
    issue: db_models.Issue
    points: db_models.IssueProperty
    formula: db_models.IssueProperty
    issue, points, formula = scored_issue

    data: t.Any = session_client.get(get_url(issue.project, path.format(issue_id=issue.id))).data
    results: t.Any = data["results"] if isinstance(data, dict) else data
    row: t.Dict[str, t.Any] = (results["none"]["results"] if isinstance(results, dict) else results)[0]

    assert {key: row[key] for key in ("type_id", "custom_properties", "formula_values", "formula_errors")} == {
        "type_id": issue.type_id,
        "custom_properties": {str(points.id): 4},
        "formula_values": {str(formula.id): 25.0},
        "formula_errors": {},
    }


def test_sub_issue_rows_carry_type_and_values(
    session_client: api_test.APIClient,
    scored_issue: t.Tuple[db_models.Issue, db_models.IssueProperty, db_models.IssueProperty],
) -> None:
    child: db_models.Issue
    points: db_models.IssueProperty
    child, points, _ = scored_issue
    parent: db_models.Issue = create_issue(session_client, child.project, {})
    patch_issue(session_client, child, {"parent_id": str(parent.id)})

    response: api_response.Response = session_client.get(get_url(parent.project, f"issues/{parent.id}/sub-issues/"))

    row: t.Dict[str, t.Any] = response.data["sub_issues"][0]
    assert (row["type_id"], row["custom_properties"]) == (child.type_id, {str(points.id): 4})


def test_work_item_without_type_has_no_values(
    session_client: api_test.APIClient, plain_project: db_models.Project
) -> None:
    response: api_response.Response = post_issue(session_client, plain_project, {})

    assert {
        key: response.data[key] for key in ("type_id", "custom_properties", "formula_values", "formula_errors")
    } == {
        "type_id": None,
        "custom_properties": {},
        "formula_values": {},
        "formula_errors": {},
    }


# Drafts


def test_draft_may_leave_a_mandatory_property_empty(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    create_property(task, PropertyType.DECIMAL, display_name="Score", is_required=True)
    note: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Note")

    response: api_response.Response = post_draft(session_client, project, {"custom_properties": {str(note.id): "x"}})

    assert (response.status_code, response.data.get("type_id"), response.data.get("custom_properties")) == (
        201,
        task.id,
        {str(note.id): "x"},
    )


def test_draft_update_writes_the_supplied_values_over_the_stored_ones(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    kept: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Kept")
    added: db_models.IssueProperty = create_property(task, PropertyType.TEXT, display_name="Added")
    draft_id: str = post_draft(session_client, project, {"custom_properties": {str(kept.id): "old"}}).data["id"]

    response: api_response.Response = session_client.patch(
        f"/api/workspaces/{project.workspace.slug}/draft-issues/{draft_id}/",
        {"custom_properties": {str(added.id): "new"}},
        format="json",
    )

    assert response.status_code == 204, response.data
    assert db_models.DraftIssue.objects.get(pk=draft_id).custom_properties == {
        str(kept.id): "old",
        str(added.id): "new",
    }


def test_null_type_leaves_the_type_of_a_draft_alone(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> None:
    draft_id: str = post_draft(session_client, project, {}).data["id"]

    response: api_response.Response = session_client.patch(
        f"/api/workspaces/{project.workspace.slug}/draft-issues/{draft_id}/", {"type_id": None}, format="json"
    )

    assert (response.status_code, db_models.DraftIssue.objects.get(pk=draft_id).type_id) == (204, task.id)


@pytest.fixture
def scored_draft(
    session_client: api_test.APIClient, project: db_models.Project, task: db_models.IssueType
) -> t.Tuple[str, db_models.IssueProperty]:
    """The conversion url of a draft whose type has the mandatory property Score, and that property."""
    score: db_models.IssueProperty = create_property(task, PropertyType.DECIMAL, display_name="Score", is_required=True)
    draft_id: str = post_draft(session_client, project, {}).data["id"]
    return f"/api/workspaces/{project.workspace.slug}/draft-to-issue/{draft_id}/", score


def test_draft_without_a_mandatory_value_stays_a_draft(
    session_client: api_test.APIClient, scored_draft: t.Tuple[str, db_models.IssueProperty]
) -> None:
    url: str
    score: db_models.IssueProperty
    url, score = scored_draft

    response: api_response.Response = session_client.post(url, {"name": "Draft"}, format="json")

    assert (response.status_code, response.json(), db_models.DraftIssue.objects.count()) == (
        400,
        {"custom_properties": {str(score.id): ["Score is mandatory."]}},
        1,
    )


def test_draft_with_its_mandatory_values_becomes_a_work_item(
    session_client: api_test.APIClient, scored_draft: t.Tuple[str, db_models.IssueProperty]
) -> None:
    url: str
    score: db_models.IssueProperty
    url, score = scored_draft

    response: api_response.Response = session_client.post(
        url, {"name": "Draft", "custom_properties": {str(score.id): 5}}, format="json"
    )

    assert (response.status_code, list(db_models.Issue.objects.values_list("name", "custom_properties"))) == (
        201,
        [("Draft", {str(score.id): 5})],
    )


def test_draft_that_became_a_work_item_is_gone(
    session_client: api_test.APIClient, scored_draft: t.Tuple[str, db_models.IssueProperty]
) -> None:
    url: str
    score: db_models.IssueProperty
    url, score = scored_draft

    session_client.post(url, {"name": "Draft", "custom_properties": {str(score.id): 5}}, format="json")

    assert not db_models.DraftIssue.objects.exists()
