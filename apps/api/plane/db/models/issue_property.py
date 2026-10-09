# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.db.models as django_models

import plane.db.models.project as project_models


class IssueProperty(project_models.ProjectBaseModel):
    # The values and the field names below are the ones the Plane SDK sends and expects
    # (plane.models.enums.PropertyType, plane.models.work_item_properties.WorkItemProperty),
    # so neither API translates. A member picker is RELATION with relation_type USER and
    # a rich text property is RELATION with relation_type RICH_TEXT.
    class PropertyType(django_models.TextChoices):
        TEXT = "TEXT", "Text"
        DECIMAL = "DECIMAL", "Number"
        OPTION = "OPTION", "Dropdown"
        BOOLEAN = "BOOLEAN", "Boolean"
        DATETIME = "DATETIME", "Date"
        RELATION = "RELATION", "Relation"
        URL = "URL", "URL"
        FORMULA = "FORMULA", "Formula"
        CASCADING = "CASCADING", "Cascading"

    class RelationType(django_models.TextChoices):
        USER = "USER", "Member picker"
        RICH_TEXT = "RICH_TEXT", "Rich text"

    issue_type = django_models.ForeignKey("db.IssueType", on_delete=django_models.CASCADE, related_name="properties")
    display_name = django_models.CharField(max_length=255)
    description = django_models.TextField(blank=True)
    logo_props = django_models.JSONField(default=dict)
    sort_order = django_models.FloatField(default=65535)
    property_type = django_models.CharField(max_length=255, choices=PropertyType.choices)
    relation_type = django_models.CharField(max_length=255, choices=RelationType.choices, null=True, blank=True)
    is_required = django_models.BooleanField(default=False)
    is_active = django_models.BooleanField(default=True)
    is_multi = django_models.BooleanField(default=False)
    # A list of strings, as the SDK has it: the number of a DECIMAL property, the member ids
    # of a member picker, the fixed text of a read-only TEXT property. The default of a
    # dropdown is IssuePropertyOption.is_default.
    default_value = django_models.JSONField(default=list, blank=True)
    # {"display_format": ...} for TEXT and DATETIME, {"expression": ...} for FORMULA,
    # {"levels": [{"name": ..., "is_required": ...}, ...]} for CASCADING.
    settings = django_models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Issue Property"
        verbose_name_plural = "Issue Properties"
        db_table = "issue_properties"
        ordering = ("sort_order",)
        constraints = [
            django_models.UniqueConstraint(
                fields=["issue_type", "display_name"],
                condition=django_models.Q(deleted_at__isnull=True),
                name="issue_property_unique_type_name_when_deleted_at_null",
            )
        ]

    def save(self, *args: t.Any, **kwargs: t.Any) -> None:
        if self._state.adding:
            largest: t.Optional[float] = IssueProperty.objects.filter(issue_type=self.issue_type).aggregate(
                largest=django_models.Max("sort_order")
            )["largest"]
            if largest is not None:
                self.sort_order = largest + 10000
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.display_name


class IssuePropertyOption(project_models.ProjectBaseModel):
    property = django_models.ForeignKey(IssueProperty, on_delete=django_models.CASCADE, related_name="options")
    # The option of the level above, for an option of a cascading property below its first level.
    parent = django_models.ForeignKey(
        "self", on_delete=django_models.CASCADE, null=True, blank=True, related_name="children"
    )
    name = django_models.CharField(max_length=255)
    # What the options under this one are called in place of the name of their level.
    sub_level_label = django_models.CharField(max_length=100, blank=True)
    sort_order = django_models.FloatField(default=65535)
    logo_props = django_models.JSONField(default=dict)
    is_default = django_models.BooleanField(default=False)

    class Meta:
        verbose_name = "Issue Property Option"
        verbose_name_plural = "Issue Property Options"
        db_table = "issue_property_options"
        ordering = ("sort_order",)
        constraints = [
            django_models.UniqueConstraint(
                fields=["property", "name"],
                condition=django_models.Q(parent__isnull=True, deleted_at__isnull=True),
                name="issue_property_option_unique_name_when_deleted_at_null",
            ),
            django_models.UniqueConstraint(
                fields=["parent", "name"],
                condition=django_models.Q(deleted_at__isnull=True),
                name="issue_property_option_unique_parent_name_when_deleted_at_null",
            ),
        ]

    def save(self, *args: t.Any, **kwargs: t.Any) -> None:
        if self._state.adding:
            largest: t.Optional[float] = IssuePropertyOption.objects.filter(property=self.property).aggregate(
                largest=django_models.Max("sort_order")
            )["largest"]
            if largest is not None:
                self.sort_order = largest + 10000
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
