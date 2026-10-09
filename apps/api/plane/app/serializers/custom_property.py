# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import rest_framework.serializers as api_serializers

import plane.app.serializers.base as base_serializers
import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties

PropertyType: t.TypeAlias = db_models.IssueProperty.PropertyType
RelationType: t.TypeAlias = db_models.IssueProperty.RelationType

READ_ONLY_FIELDS: t.List[str] = ["workspace", "created_by", "updated_by", "created_at", "updated_at", "deleted_at"]


class IssueTypeSerializer(base_serializers.BaseSerializer):
    class Meta:
        model = db_models.IssueType
        fields = "__all__"
        read_only_fields = [*READ_ONLY_FIELDS, "is_epic"]

    def validate(self, attrs: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        if (
            "name" in attrs
            and custom_properties.get_project_issue_types(self.context["project_id"])
            .filter(name__iexact=attrs["name"])
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            raise api_serializers.ValidationError({"name": "The project already has a work item type with this name."})
        is_default: bool = attrs.get("is_default", getattr(self.instance, "is_default", False))
        if is_default and not attrs.get("is_active", getattr(self.instance, "is_active", True)):
            raise api_serializers.ValidationError({"is_active": "The default type cannot be disabled."})
        if getattr(self.instance, "is_default", False) and not is_default:
            raise api_serializers.ValidationError({"is_default": "Make another type the default instead."})
        return attrs


class IssuePropertyOptionSerializer(base_serializers.BaseSerializer):
    class Meta:
        model = db_models.IssuePropertyOption
        fields = "__all__"
        read_only_fields = [*READ_ONLY_FIELDS, "project", "property"]

    def validate(self, attrs: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        parent: t.Optional[db_models.IssuePropertyOption] = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent != getattr(self.instance, "parent", None):
            if parent is not None and parent.property_id != self.context.get("property_id"):
                raise api_serializers.ValidationError({"parent": "Choose an option of the property."})
            parent_ids: t.Dict[str, t.Optional[str]] = custom_properties.get_parent_ids(
                (parent or self.instance).property
            )
            level_index: int = (
                0 if parent is None else custom_properties.get_level_index(parent_ids, str(parent.id)) + 1
            )
            if self.instance:
                # A moved option stays on its level, and so do the options under it.
                if level_index != custom_properties.get_level_index(parent_ids, str(self.instance.id)):
                    raise api_serializers.ValidationError(
                        {"parent": "An option moves only to another option of the level above it."}
                    )
            elif level_index >= len(parent.property.settings.get("levels", [])):
                raise api_serializers.ValidationError(
                    {"parent": "Choose an option of the property that is above its last level."}
                )
        if (
            db_models.IssuePropertyOption.objects.filter(
                property_id=self.context.get("property_id"),
                parent=parent,
                name__iexact=attrs.get("name", getattr(self.instance, "name", None)),
            )
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            raise api_serializers.ValidationError({"name": "The property already has an option with this name."})
        return attrs


class TextSettingsSerializer(api_serializers.Serializer):
    display_format = api_serializers.ChoiceField(choices=["single-line", "multi-line", "readonly"])


class DateSettingsSerializer(api_serializers.Serializer):
    display_format = api_serializers.ChoiceField(choices=["MMM dd, yyyy", "dd/MM/yyyy", "MM/dd/yyyy", "yyyy/MM/dd"])


class FormulaSettingsSerializer(api_serializers.Serializer):
    expression = api_serializers.CharField()


class CascadingLevelSerializer(api_serializers.Serializer):
    name = api_serializers.CharField(max_length=100)
    is_required = api_serializers.BooleanField(default=False)


class CascadingSettingsSerializer(api_serializers.Serializer):
    levels = CascadingLevelSerializer(many=True, min_length=2, max_length=4)

    def validate_levels(self, levels: t.List[t.Dict[str, t.Any]]) -> t.List[t.Dict[str, t.Any]]:
        # The docs: making a level mandatory also makes every level above it mandatory.
        is_required: bool = False
        level: t.Dict[str, t.Any]
        for level in reversed(levels):
            is_required = level["is_required"] = level["is_required"] or is_required
        return levels


class IssuePropertySerializer(base_serializers.BaseSerializer):
    default_value = api_serializers.ListField(child=api_serializers.CharField(), required=False)
    options = IssuePropertyOptionSerializer(many=True, read_only=True)

    class Meta:
        model = db_models.IssueProperty
        fields = "__all__"
        read_only_fields = [*READ_ONLY_FIELDS, "project", "issue_type"]

    SETTINGS_SERIALIZERS: t.Dict[str, t.Type[api_serializers.Serializer]] = {
        PropertyType.TEXT: TextSettingsSerializer,
        PropertyType.DATETIME: DateSettingsSerializer,
        PropertyType.FORMULA: FormulaSettingsSerializer,
        PropertyType.CASCADING: CascadingSettingsSerializer,
    }
    # The SDK cannot send the settings of a cascading property: it creates one with the levels the docs start with.
    DEFAULT_SETTINGS: t.Dict[str, t.Dict[str, t.Any]] = {
        PropertyType.CASCADING: {"levels": [{"name": "Level 1"}, {"name": "Level 2"}]}
    }
    # Stored values have the shape these three give them.
    FIELDS_FIXED_AT_CREATION: t.Tuple[str, ...] = ("property_type", "relation_type", "is_multi")

    def validate(self, attrs: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        current: db_models.IssueProperty = self.instance or db_models.IssueProperty(
            issue_type_id=self.context.get("type_id")
        )
        field: str
        for field in self.FIELDS_FIXED_AT_CREATION:
            if self.instance and attrs.get(field, getattr(current, field)) != getattr(current, field):
                raise api_serializers.ValidationError({field: "This cannot change after the property is created."})
        property_type: str = attrs.get("property_type", current.property_type)
        relation_type: t.Optional[str] = attrs.get("relation_type", current.relation_type)
        if property_type != PropertyType.RELATION:
            relation_type = attrs["relation_type"] = None
        elif not relation_type:
            raise api_serializers.ValidationError({"relation_type": "Choose USER or RICH_TEXT."})

        other_properties: t.List[db_models.IssueProperty] = list(
            db_models.IssueProperty.objects.filter(issue_type_id=current.issue_type_id).exclude(pk=current.pk)
        )
        display_name: str = attrs.get("display_name", current.display_name)
        if any(property.display_name.lower() == display_name.lower() for property in other_properties):
            raise api_serializers.ValidationError(
                {"display_name": "The work item type already has a property with this name."}
            )

        settings: t.Dict[str, str] = current.settings
        # Settings the request does not send are not validated again, so that a formula whose
        # source was renamed can still be renamed or switched inactive.
        if "settings" in attrs or not self.instance:
            settings = {}
            if property_type in self.SETTINGS_SERIALIZERS:
                settings_serializer: api_serializers.Serializer = self.SETTINGS_SERIALIZERS[property_type](
                    data=attrs.get("settings", self.DEFAULT_SETTINGS.get(property_type, {}))
                )
                if not settings_serializer.is_valid():
                    raise api_serializers.ValidationError({"settings": settings_serializer.errors})
                settings = dict(settings_serializer.validated_data)
            if property_type == PropertyType.FORMULA:
                custom_properties.validate_formula(settings["expression"], other_properties)
            # The docs: the format of a text property cannot be changed after creation. A switch
            # to read-only would also leave stored values that nobody can write or clear.
            if self.instance and property_type == PropertyType.TEXT and settings != current.settings:
                raise api_serializers.ValidationError(
                    {"settings": {"display_format": ["This cannot change after the property is created."]}}
                )
            attrs["settings"] = settings

        if attrs.get("is_required", current.is_required) and (
            property_type in (PropertyType.BOOLEAN, PropertyType.FORMULA, PropertyType.CASCADING)
            or settings.get("display_format") == "readonly"
        ):
            raise api_serializers.ValidationError({"is_required": "This property cannot be mandatory."})

        if "default_value" in attrs:
            error: api_serializers.ValidationError
            try:
                if property_type == PropertyType.DECIMAL:
                    api_serializers.ListField(child=api_serializers.FloatField(), max_length=1).run_validation(
                        attrs["default_value"]
                    )
                elif relation_type == RelationType.USER:
                    # A default is copied into every new work item without another check.
                    member_picker: db_models.IssueProperty = db_models.IssueProperty(
                        property_type=property_type, relation_type=relation_type
                    )
                    member_id: str
                    for member_id in attrs["default_value"]:
                        custom_properties.validate_property_value(member_picker, member_id, self.context["project_id"])
            except api_serializers.ValidationError as error:
                raise api_serializers.ValidationError({"default_value": error.detail})
        return attrs
