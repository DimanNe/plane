# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.db.models as django_models

import plane.db.models as db_models

# A condition on a custom property has the key customproperty_<property id>__<lookup>: the web
# writes it, and the hooks of ComplexFilterBackend are documented with it. A filterset cannot
# declare a filter per property, so IssueFilterSet declares customproperty_value__<lookup> and
# the property id travels in the value, in front of the comma-separated values the web sends.
KEY_PREFIX: str = "customproperty_"


def get_custom_property_filter_name(key: str) -> str:
    """Returns the filter of IssueFilterSet that takes the condition with this key; another key as it is."""
    if not key.startswith(KEY_PREFIX):
        return key
    return f"customproperty_value__{key.rpartition('__')[2]}"


def get_custom_property_filter_conditions(conditions: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Returns the conditions of one filter object as IssueFilterSet takes them."""
    filter_conditions: t.Dict[str, t.Any] = {}
    key: str
    value: t.Any
    for key, value in conditions.items():
        if key.startswith(KEY_PREFIX):
            property_id: str = key.removeprefix(KEY_PREFIX).rpartition("__")[0]
            value = f"{property_id},{value}"
        filter_conditions[get_custom_property_filter_name(key)] = value
    return filter_conditions


def get_custom_property_q(filter_name: str, value: t.List[str]) -> django_models.Q:
    """
    Returns the condition on Issue.custom_properties for the value of a customproperty_value__<lookup> filter.

    Nothing matches a property that has been deleted: the values of its work items stay stored,
    and a saved view may still hold a condition on it.

    A work item without a value for the property has to fail the condition, not leave it NULL,
    or the negation of the condition would miss the work item as well. So a value is looked for
    in the whole column, by jsonb containment, and a range first asks for the key.
    """
    property_id: str
    values: t.List[str]
    property_id, *values = value
    issue_property: t.Optional[db_models.IssueProperty] = db_models.IssueProperty.objects.filter(pk=property_id).first()
    if issue_property is None:
        return django_models.Q(pk__in=[])
    if filter_name.endswith("__range"):
        stored_value: str = f"custom_properties__{property_id}"
        return django_models.Q(
            custom_properties__has_key=property_id,
            **{f"{stored_value}__gte": values[0], f"{stored_value}__lte": values[-1]},
        )
    if issue_property.property_type == db_models.IssueProperty.PropertyType.BOOLEAN:
        # A checkbox nobody ticked stores nothing, so "no" is every work item of the property's type that is not "yes".
        is_checked: django_models.Q = django_models.Q(custom_properties__contains={property_id: True})
        if values[0].lower() == "true":
            return is_checked
        return django_models.Q(type_id=issue_property.issue_type_id) & ~is_checked
    has_any_value: django_models.Q = django_models.Q()
    given: str
    for given in values:
        has_any_value |= django_models.Q(
            custom_properties__contains={property_id: [given] if issue_property.is_multi else given}
        )
    return has_any_value
