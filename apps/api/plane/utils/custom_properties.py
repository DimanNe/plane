# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import collections
import datetime
import functools
import html
import math
import typing as t
import uuid

import django.db.models as django_models
import django.utils.html as django_html
import rest_framework.exceptions as api_exceptions
import rest_framework.serializers as api_serializers

import plane.db.models as db_models
import plane.utils.content_validator as content_validator
import plane.utils.property_formula as property_formula

PropertyType: t.TypeAlias = db_models.IssueProperty.PropertyType
RelationType: t.TypeAlias = db_models.IssueProperty.RelationType

# Property id -> value, as Issue.custom_properties and DraftIssue.custom_properties store it:
# text, URL and rich text (sanitized HTML) as a string, a number, a boolean, a date as
# "YYYY-MM-DD", an option or member id as a string, several of them as a list. The value of
# a cascading property is the list of the option ids chosen on its levels, first level first.
PropertyValues: t.TypeAlias = t.Dict[str, property_formula.JsonValue]
WorkItem: t.TypeAlias = t.Union[db_models.Issue, db_models.DraftIssue]

SCALAR_VALUE_FIELDS: t.Dict[str, api_serializers.Field] = {
    PropertyType.TEXT: api_serializers.CharField(),
    PropertyType.DECIMAL: api_serializers.FloatField(),
    PropertyType.BOOLEAN: api_serializers.BooleanField(),
    PropertyType.DATETIME: api_serializers.DateField(),
    PropertyType.URL: api_serializers.URLField(),
}

# What a formula may read, as the docs have it: Text, Number, Date and Boolean properties of its type.
FORMULA_SOURCE_TYPES: t.Tuple[str, ...] = (
    PropertyType.TEXT,
    PropertyType.DECIMAL,
    PropertyType.DATETIME,
    PropertyType.BOOLEAN,
)


def get_project_issue_types(project_id: t.Union[str, uuid.UUID, None]) -> django_models.QuerySet[db_models.IssueType]:
    """
    Returns the work item types of a project.

    Every project has type rows of its own, and its link to one is what makes the row a type of
    the project: deleting a type removes the link and keeps the row for the work items that
    still have the type.
    """
    return db_models.IssueType.objects.filter(
        project_issue_types__project_id=project_id, project_issue_types__deleted_at__isnull=True
    )


def enable_project_types(project: db_models.Project) -> None:
    """
    Creates the Task (default) and Epic types of a project whose types have just been enabled.

    ProjectTypesSerializerMixin calls this after every save of a project, so it does nothing for
    a project that has its types. Epic is an ordinary type: upstream's is_epic flag stays off,
    because upstream list queries hide work items of is_epic types.
    """
    if not project.is_issue_type_enabled or get_project_issue_types(project.id).exists():
        return
    name: str
    for name in ("Task", "Epic"):
        issue_type: db_models.IssueType = db_models.IssueType.objects.create(
            workspace_id=project.workspace_id, name=name, is_default=name == "Task"
        )
        db_models.ProjectIssueType.objects.create(project=project, issue_type=issue_type)
        if issue_type.is_default:
            db_models.Issue.objects.filter(project=project, type__isnull=True).update(type=issue_type)
            db_models.DraftIssue.objects.filter(project=project, type__isnull=True).update(type=issue_type)


class ProjectTypesSerializerMixin:
    """
    For the serializers that write Project.is_issue_type_enabled: the docs say that types cannot
    be switched off again, and switching them on has to create the types of the project.
    """

    def validate_is_issue_type_enabled(self, value: bool) -> bool:
        if self.instance and self.instance.is_issue_type_enabled and not value:
            raise api_exceptions.ValidationError("Work item types cannot be disabled once enabled.")
        return value

    # The name the SDK gives the field, which the feature serializer of /api/v1/ uses.
    validate_work_item_types = validate_is_issue_type_enabled

    def save(self, **kwargs: t.Any) -> db_models.Project:
        project: db_models.Project = super().save(**kwargs)
        enable_project_types(project)
        return project


def get_type_properties(type_id: t.Optional[uuid.UUID]) -> t.List[db_models.IssueProperty]:
    if type_id is None:
        return []
    return list(db_models.IssueProperty.objects.filter(issue_type_id=type_id).prefetch_related("options"))


def is_read_only_text(property: db_models.IssueProperty) -> bool:
    return property.property_type == PropertyType.TEXT and property.settings.get("display_format") == "readonly"


def get_selected_ids(value: property_formula.JsonValue) -> t.List[property_formula.JsonValue]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def get_parent_ids(property: db_models.IssueProperty) -> t.Dict[str, t.Optional[str]]:
    """Returns option id -> id of the option above it, None for an option of the first level."""
    return {str(option.id): option.parent_id and str(option.parent_id) for option in property.options.all()}


def get_level_index(parent_ids: t.Dict[str, t.Optional[str]], option_id: str) -> int:
    """Returns the index, in the levels of a cascading property, of the level an option is on."""
    parent_id: t.Optional[str] = parent_ids[option_id]
    return 0 if parent_id is None else get_level_index(parent_ids, parent_id) + 1


def get_stored_number(value: float) -> t.Union[int, float]:
    """A whole number is stored as an integer: as a float, 3 reads "3.0" wherever a value becomes text."""
    return int(value) if value.is_integer() else value


def validate_property_value(
    property: db_models.IssueProperty, value: property_formula.JsonValue, project_id: t.Optional[uuid.UUID]
) -> property_formula.JsonValue:
    """Returns the value as it is stored, None for an empty one."""
    if value is None or value == "" or value == []:
        return None
    if property.property_type == PropertyType.FORMULA or is_read_only_text(property):
        raise api_exceptions.ValidationError("This property is read-only.")
    field: t.Optional[api_serializers.Field] = SCALAR_VALUE_FIELDS.get(property.property_type)
    if field is not None:
        validated: t.Union[str, float, bool, datetime.date] = field.run_validation(value)
        if isinstance(validated, float):
            if not math.isfinite(validated):
                raise api_exceptions.ValidationError("A valid number is required.")
            return get_stored_number(validated)
        return validated.isoformat() if isinstance(validated, datetime.date) else validated
    if property.relation_type == RelationType.RICH_TEXT:
        if not isinstance(value, str):
            raise api_exceptions.ValidationError("Expected HTML text.")
        is_valid: bool
        error_message: t.Optional[str]
        sanitized_html: t.Optional[str]
        is_valid, error_message, sanitized_html = content_validator.validate_html_content(value)
        if not is_valid:
            raise api_exceptions.ValidationError(error_message)
        if sanitized_html is not None:
            value = sanitized_html
        has_image: bool = "<img" in value or "<image-component" in value
        return value if has_image or django_html.strip_tags(value).strip() else None
    selected: t.List[str] = list(dict.fromkeys(str(item) for item in get_selected_ids(value)))
    if property.property_type == PropertyType.CASCADING:
        parent_ids: t.Dict[str, t.Optional[str]] = get_parent_ids(property)
        # "" stands in for an id that is no option of the property: no option is under it
        if [parent_ids.get(item, "") for item in selected] != [None, *selected[:-1]]:
            raise api_exceptions.ValidationError(
                "Choose one option for each level from the first, each under the one before."
            )
        return selected
    if not property.is_multi and len(selected) != 1:
        raise api_exceptions.ValidationError("Expected one selection.")
    allowed: t.Set[str]
    if property.property_type == PropertyType.OPTION:
        allowed = {str(option.id) for option in property.options.all()}
    else:
        allowed = {
            str(member_id)
            for member_id in db_models.ProjectMember.objects.filter(project_id=project_id, is_active=True).values_list(
                "member_id", flat=True
            )
        }
    if not set(selected) <= allowed:
        raise api_exceptions.ValidationError(
            "Choose from the options of the property."
            if property.property_type == PropertyType.OPTION
            else "Choose from the members of the project."
        )
    return selected if property.is_multi else selected[0]


def validate_supplied_values(
    properties: t.List[db_models.IssueProperty],
    supplied: property_formula.JsonValue,
    project_id: t.Optional[uuid.UUID],
) -> PropertyValues:
    if not isinstance(supplied, dict):
        raise api_exceptions.ValidationError({"custom_properties": ["Expected an object keyed by property id."]})
    properties_by_id: t.Dict[str, db_models.IssueProperty] = {str(property.id): property for property in properties}
    validated: PropertyValues = {}
    key: str
    value: property_formula.JsonValue
    for key, value in supplied.items():
        property: t.Optional[db_models.IssueProperty] = properties_by_id.get(key)
        error: api_exceptions.ValidationError
        try:
            if property is None or not property.is_active:
                raise api_exceptions.ValidationError("This is not an active property of the work item type.")
            validated[key] = validate_property_value(property, value, project_id)
        except api_exceptions.ValidationError as error:
            raise api_exceptions.ValidationError({"custom_properties": {key: error.detail}})
    return validated


def get_default_values(properties: t.List[db_models.IssueProperty]) -> PropertyValues:
    """
    Returns the values a work item starts with.

    A checkbox nobody ticked stores nothing, and readers take a missing boolean for false: a
    stored false would be moved into the description as "No" by every later change of type.
    """
    defaults: PropertyValues = {}
    property: db_models.IssueProperty
    for property in properties:
        if not property.is_active:
            continue
        if property.property_type == PropertyType.OPTION:
            option_ids: t.List[str] = [str(option.id) for option in property.options.all() if option.is_default]
            if option_ids:
                defaults[str(property.id)] = option_ids if property.is_multi else option_ids[0]
        elif property.property_type == PropertyType.DECIMAL and property.default_value:
            defaults[str(property.id)] = get_stored_number(float(property.default_value[0]))
        elif property.relation_type == RelationType.USER and property.default_value:
            defaults[str(property.id)] = property.default_value if property.is_multi else property.default_value[0]
    return defaults


def merge_values(
    values: PropertyValues,
    properties: t.List[db_models.IssueProperty],
    supplied: property_formula.JsonValue,
    project_id: t.Optional[uuid.UUID],
) -> PropertyValues:
    """Returns the values with the supplied ones validated and written over them; a supplied null clears."""
    merged: PropertyValues = {**values, **validate_supplied_values(properties, supplied, project_id)}
    return {key: value for key, value in merged.items() if value is not None}


def get_empty_mandatory_name(property: db_models.IssueProperty, value: property_formula.JsonValue) -> t.Optional[str]:
    """
    Returns the name of what a stored value leaves empty though it is mandatory: the property,
    or a level of a cascading property.

    The docs: a cascading property is not mandatory as a whole, its levels are, and a mandatory
    level needs a value only when the option above it has options under it.
    """
    if property.property_type != PropertyType.CASCADING:
        return property.display_name if property.is_required and value is None else None
    selected: t.List[property_formula.JsonValue] = get_selected_ids(value)
    levels: t.List[t.Dict[str, t.Any]] = property.settings["levels"]
    if (
        len(selected) < len(levels)
        and levels[len(selected)]["is_required"]
        and (selected[-1] if selected else None) in get_parent_ids(property).values()
    ):
        return levels[len(selected)]["name"]
    return None


def check_required_values(properties: t.Iterable[db_models.IssueProperty], values: PropertyValues) -> None:
    missing: t.Dict[str, t.List[str]] = {}
    property: db_models.IssueProperty
    for property in properties:
        name: t.Optional[str] = get_empty_mandatory_name(property, values.get(str(property.id)))
        if property.is_active and name:
            missing[str(property.id)] = [f"{name} is mandatory."]
    if missing:
        raise api_exceptions.ValidationError({"custom_properties": missing})


def validate_issue_type(issue_type: db_models.IssueType, project_id: t.Optional[uuid.UUID]) -> None:
    if not issue_type.is_active or not get_project_issue_types(project_id).filter(pk=issue_type.pk).exists():
        raise api_exceptions.ValidationError({"type_id": ["Choose an active work item type of the project."]})


def get_type_and_values_for_create(
    project_id: t.Optional[uuid.UUID],
    issue_type: t.Optional[db_models.IssueType],
    supplied: property_formula.JsonValue,
    check_required: bool,
    check_required_levels: bool = True,
) -> t.Tuple[t.Optional[db_models.IssueType], PropertyValues]:
    """
    Returns the type and the property values a new work item or draft is created with.

    Without a supplied type it is the default type of the project, and no type at all in
    a project that has not enabled types.

    `check_required` says whether every mandatory property of the type has to be filled. It is
    on where the user is shown the property inputs, which is the work item form of the web. It
    is off for a draft, which may be incomplete, for intake, whose form has no property inputs,
    and for /api/v1/, whose SDK sets values one request at a time after creation.

    `check_required_levels` is off where a draft becomes a work item. Cascading properties are
    not available on drafts, so a mandatory level cannot have been filled there.
    """
    if issue_type is None:
        issue_type = get_project_issue_types(project_id).filter(is_default=True).first()
    else:
        validate_issue_type(issue_type, project_id)
    properties: t.List[db_models.IssueProperty] = get_type_properties(issue_type.id if issue_type else None)
    values: PropertyValues = merge_values(get_default_values(properties), properties, supplied, project_id)
    if check_required:
        check_required_values(
            [
                property
                for property in properties
                if check_required_levels or property.property_type != PropertyType.CASCADING
            ],
            values,
        )
    return issue_type, values


def format_value_as_text(property: db_models.IssueProperty, value: property_formula.JsonValue) -> str:
    names: t.Dict[str, str]
    if property.property_type in (PropertyType.OPTION, PropertyType.CASCADING):
        names = {str(option.id): option.name for option in property.options.all()}
        separator: str = ", " if property.property_type == PropertyType.OPTION else " / "
        return separator.join(names.get(str(item), str(item)) for item in get_selected_ids(value))
    if property.relation_type == RelationType.USER:
        names = {
            str(user_id): display_name
            for user_id, display_name in db_models.User.objects.filter(id__in=get_selected_ids(value)).values_list(
                "id", "display_name"
            )
        }
        return ", ".join(names.get(str(item), str(item)) for item in get_selected_ids(value))
    if property.property_type == PropertyType.BOOLEAN:
        return "Yes" if value else "No"
    return str(value)


def append_value_to_description(
    description_html: t.Optional[str], property: db_models.IssueProperty, value: property_formula.JsonValue
) -> str:
    label: str = html.escape(property.display_name)
    if property.relation_type == RelationType.RICH_TEXT:
        return f"{description_html or ''}<p>{label}:</p>{value}"
    return f"{description_html or ''}<p>{label}: {html.escape(format_value_as_text(property, value))}</p>"


def subscribe_selected_members(
    issue: db_models.Issue,
    properties: t.Iterable[db_models.IssueProperty],
    values: PropertyValues,
    previous_values: PropertyValues,
) -> None:
    """
    The docs promise that a member selected in a member picker starts to follow the work item.

    `properties` are those of the type the values belong to; during a change of type the work
    item row still has the old type.
    """
    property: db_models.IssueProperty
    for property in properties:
        if property.relation_type != RelationType.USER:
            continue
        member_id: property_formula.JsonValue
        for member_id in get_selected_ids(values.get(str(property.id))):
            if member_id not in get_selected_ids(previous_values.get(str(property.id))):
                db_models.IssueSubscriber.objects.get_or_create(
                    issue=issue, subscriber_id=member_id, project_id=issue.project_id
                )


def get_changes_for_update(
    work_item: WorkItem,
    issue_type: t.Optional[db_models.IssueType],
    supplied: property_formula.JsonValue,
    description_html: t.Optional[str],
    check_required: bool,
) -> t.Dict[str, t.Any]:
    """
    Returns the fields an update has to write for a supplied type and supplied property values.

    Two writers that set different properties of one work item would otherwise each save
    the map they read and lose the other's value, so the row is locked and the supplied
    values go over the values of the locked row: call this inside the transaction that saves.

    Only a type that differs from the stored one is written, so a supplied null leaves the type
    alone. The change moves the values of the old type's properties into the description as
    text, as the docs describe; `description_html` is the description the same request sets,
    if it sets one.

    `check_required` is off for the same callers as in get_type_and_values_for_create. A change
    of type checks every mandatory property of the new type. A write of values checks only the
    properties it supplies, so that it cannot clear a mandatory one: the web saves one property
    at a time, and a mandatory property that was added to the type later would otherwise block
    every other property of the work item until it is filled.
    """
    if supplied == {} and (issue_type is None or issue_type.id == work_item.type_id):
        return {}
    locked: WorkItem = type(work_item).objects.select_for_update().get(pk=work_item.pk)
    changes: t.Dict[str, t.Any] = {}
    properties: t.List[db_models.IssueProperty]
    checked_properties: t.List[db_models.IssueProperty]
    if issue_type is None or issue_type.id == locked.type_id:
        properties = get_type_properties(locked.type_id)
        changes["custom_properties"] = merge_values(locked.custom_properties, properties, supplied, locked.project_id)
        checked_properties = [property for property in properties if str(property.id) in supplied]
    else:
        validate_issue_type(issue_type, locked.project_id)
        changes["type"] = issue_type
        changes["description_html"] = locked.description_html if description_html is None else description_html
        property: db_models.IssueProperty
        for property in get_type_properties(locked.type_id):
            if str(property.id) in locked.custom_properties:
                changes["description_html"] = append_value_to_description(
                    changes["description_html"], property, locked.custom_properties[str(property.id)]
                )
        properties = get_type_properties(issue_type.id)
        changes["custom_properties"] = merge_values(
            get_default_values(properties), properties, supplied, locked.project_id
        )
        checked_properties = properties
    if check_required:
        check_required_values(checked_properties, changes["custom_properties"])
    if isinstance(locked, db_models.Issue):
        subscribe_selected_members(locked, properties, changes["custom_properties"], locked.custom_properties)
    return changes


def track_custom_properties(
    requested_data: t.Dict[str, t.Any],
    current_instance: t.Dict[str, t.Any],
    issue_id: str,
    project_id: str,
    workspace_id: str,
    actor_id: str,
    issue_activities: t.List[db_models.IssueActivity],
    epoch: float,
) -> None:
    """
    Appends one activity for every property whose value an update changed.

    A tracker of upstream's bgtasks.issue_activities_task, which calls it for the key
    `custom_properties` of an update: `requested_data` is the request body and `current_instance`
    the work item as it was serialized before the update. The request has the values as the
    client typed them, so the new ones are read from the saved work item.
    """
    previous_values: PropertyValues = current_instance.get("custom_properties") or {}
    values: PropertyValues = db_models.Issue.all_objects.values_list("custom_properties", flat=True).get(pk=issue_id)
    property: db_models.IssueProperty
    for property in db_models.IssueProperty.objects.filter(id__in=list(requested_data["custom_properties"])):
        key: str = str(property.id)
        if previous_values.get(key) != values.get(key):
            issue_activities.append(
                db_models.IssueActivity(
                    issue_id=issue_id,
                    actor_id=actor_id,
                    project_id=project_id,
                    workspace_id=workspace_id,
                    verb="updated",
                    field="custom_property",
                    new_identifier=property.id,
                    old_value=format_value_as_text(property, previous_values[key]) if key in previous_values else None,
                    new_value=format_value_as_text(property, values[key]) if key in values else None,
                    comment=f"updated {property.display_name} to ",
                    epoch=epoch,
                )
            )


def track_type(
    requested_data: t.Dict[str, t.Any],
    current_instance: t.Dict[str, t.Any],
    issue_id: str,
    project_id: str,
    workspace_id: str,
    actor_id: str,
    issue_activities: t.List[db_models.IssueActivity],
    epoch: float,
) -> None:
    """The tracker of bgtasks.issue_activities_task for the key `type_id` of an update."""
    old_type_id: t.Optional[str] = current_instance.get("type_id")
    new_type_id: t.Optional[str] = requested_data.get("type_id")
    if new_type_id and new_type_id != old_type_id:
        names: t.Dict[str, str] = {
            str(type_id): name
            for type_id, name in db_models.IssueType.objects.filter(
                id__in=[type_id for type_id in (old_type_id, new_type_id) if type_id]
            ).values_list("id", "name")
        }
        issue_activities.append(
            db_models.IssueActivity(
                issue_id=issue_id,
                actor_id=actor_id,
                project_id=project_id,
                workspace_id=workspace_id,
                verb="updated",
                field="type",
                old_identifier=old_type_id,
                new_identifier=new_type_id,
                old_value=names.get(str(old_type_id)),
                new_value=names.get(str(new_type_id)),
                comment="updated the type to ",
                epoch=epoch,
            )
        )


def get_formula_sources(
    properties: t.Iterable[db_models.IssueProperty], values: PropertyValues
) -> t.Dict[str, property_formula.FormulaValue]:
    """
    Returns what a formula of the type may reference: normalized name -> value.

    References are resolved by name here, at evaluation time, and nothing is stored with the
    formula: after a property is renamed, a formula that still uses the old name reports
    an unknown property until it is edited.
    """
    sources: t.Dict[str, property_formula.FormulaValue] = {}
    property: db_models.IssueProperty
    for property in properties:
        if property.property_type not in FORMULA_SOURCE_TYPES:
            continue
        value: property_formula.FormulaValue = values.get(str(property.id))
        if is_read_only_text(property):
            value = property.default_value[0] if property.default_value else None
        elif property.property_type == PropertyType.BOOLEAN:
            value = bool(value)
        elif property.property_type == PropertyType.DATETIME and value:
            value = datetime.date.fromisoformat(value)
        sources[property_formula.normalize_formula_reference_name(property.display_name)] = value
    return sources


@functools.lru_cache
def parse_formula(expression: str) -> property_formula.Formula:
    """A list evaluates the formulas of its types once for every row; each expression is parsed once."""
    return property_formula.Formula(expression)


def validate_formula(expression: str, properties: t.Iterable[db_models.IssueProperty]) -> None:
    """Refuses an expression that does not parse or references what a formula of the type cannot read."""
    message: t.Optional[str] = None
    error: property_formula.FormulaError
    try:
        unknown: t.List[str] = sorted(parse_formula(expression).references - set(get_formula_sources(properties, {})))
        if unknown:
            message = f"Unknown property: {', '.join(unknown)}."
    except property_formula.FormulaError as error:
        message = str(error)
    if message:
        raise api_exceptions.ValidationError({"settings": {"expression": [message]}})


def get_formula_payload(
    properties: t.List[db_models.IssueProperty], values: PropertyValues
) -> t.Dict[str, t.Dict[str, property_formula.JsonValue]]:
    """
    Returns what a work item response carries besides its stored values:
    {"formula_values": {property id: result or None}, "formula_errors": {property id: message}}.
    """
    formula_values: t.Dict[str, property_formula.JsonValue] = {}
    formula_errors: t.Dict[str, property_formula.JsonValue] = {}
    formulas: t.List[db_models.IssueProperty] = [
        property for property in properties if property.property_type == PropertyType.FORMULA
    ]
    if formulas:
        sources: t.Dict[str, property_formula.FormulaValue] = get_formula_sources(properties, values)
        property: db_models.IssueProperty
        for property in formulas:
            error: property_formula.FormulaError
            try:
                formula_values[str(property.id)] = parse_formula(property.settings["expression"]).evaluate(sources)
            except property_formula.FormulaError as error:
                formula_values[str(property.id)] = None
                formula_errors[str(property.id)] = str(error)
    return {"formula_values": formula_values, "formula_errors": formula_errors}


def add_formula_payload(rows: t.Iterable[t.Dict[str, t.Any]]) -> t.List[t.Dict[str, t.Any]]:
    """Adds the formula payload to the work item rows of a list response, which carry type_id and custom_properties."""
    rows = list(rows)
    properties_by_type: t.DefaultDict[t.Optional[uuid.UUID], t.List[db_models.IssueProperty]] = collections.defaultdict(
        list
    )
    property: db_models.IssueProperty
    for property in db_models.IssueProperty.objects.filter(issue_type_id__in={row["type_id"] for row in rows}):
        properties_by_type[property.issue_type_id].append(property)
    row: t.Dict[str, t.Any]
    for row in rows:
        row.update(get_formula_payload(properties_by_type[row["type_id"]], row["custom_properties"]))
    return rows


class FormulaPayloadSerializerMixin:
    """
    Adds the formula payload to a serialized work item that includes custom_properties.

    A list serializes many work items with one instance of the serializer, so the properties
    of each type are read once per instance instead of once per work item.
    """

    @functools.cached_property
    def properties_by_type(self) -> t.Dict[t.Optional[uuid.UUID], t.List[db_models.IssueProperty]]:
        return {}

    def to_representation(self, instance: db_models.Issue) -> t.Dict[str, t.Any]:
        data: t.Dict[str, t.Any] = super().to_representation(instance)
        if "custom_properties" in data:
            if instance.type_id not in self.properties_by_type:
                self.properties_by_type[instance.type_id] = get_type_properties(instance.type_id)
            data.update(get_formula_payload(self.properties_by_type[instance.type_id], instance.custom_properties))
        return data


def get_work_items_using_option(
    model: t.Type[WorkItem], option: db_models.IssuePropertyOption
) -> django_models.QuerySet[WorkItem]:
    # jsonb containment holds both for a single selection equal to the id and for a list that has it.
    return model.objects.filter(**{f"custom_properties__{option.property_id}__contains": str(option.id)})


def remove_option_from_work_items(option: db_models.IssuePropertyOption) -> None:
    """
    Moves the option out of every work item and draft that selected it, into the description as text.

    A selection of a cascading property loses the options chosen under the option with it.
    """
    key: str = str(option.property_id)
    property: db_models.IssueProperty = db_models.IssueProperty.objects.prefetch_related("options").get(pk=key)
    model: t.Type[WorkItem]
    for model in (db_models.Issue, db_models.DraftIssue):
        work_item: WorkItem
        for work_item in get_work_items_using_option(model, option).select_for_update():
            selected: t.List[property_formula.JsonValue] = get_selected_ids(work_item.custom_properties[key])
            removed: t.List[property_formula.JsonValue] = [str(option.id)]
            if property.property_type == PropertyType.CASCADING:
                removed = selected[selected.index(str(option.id)) :]
            remaining: t.List[property_formula.JsonValue] = [item for item in selected if item not in removed]
            if remaining:
                work_item.custom_properties[key] = remaining
            else:
                del work_item.custom_properties[key]
            work_item.description_html = append_value_to_description(work_item.description_html, property, removed)
            work_item.save(
                update_fields=["custom_properties", "description_html", "description_stripped", "updated_at"]
            )


def delete_option(option: db_models.IssuePropertyOption) -> None:
    """
    Deletes an option that remove_option_from_work_items has moved out of the work items, with the
    options under it.

    Upstream soft-deletes what belongs to a deleted object in a background task; until it had
    run, the options under a deleted option would stay in the list of the property.
    """
    child: db_models.IssuePropertyOption
    for child in option.children.all():
        delete_option(child)
    option.delete()


def delete_options_below_last_level(property: db_models.IssueProperty) -> None:
    """
    The docs: deleting a level of a cascading property deletes every level below it and all their
    options, and the values move into the description as they do when an option is removed.

    Levels are deleted by saving fewer of them, so this runs after an update of the property.
    """
    parent_ids: t.Dict[str, t.Optional[str]] = get_parent_ids(property)
    option: db_models.IssuePropertyOption
    for option in property.options.all():
        if get_level_index(parent_ids, str(option.id)) == len(property.settings["levels"]):
            remove_option_from_work_items(option)
            delete_option(option)
