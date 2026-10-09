# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.db.models as django_models
import django.db.transaction as django_transaction
import rest_framework.exceptions as api_exceptions
import rest_framework.permissions as api_permissions
import rest_framework.request as api_request
import rest_framework.response as api_response

import plane.app.permissions as app_permissions
import plane.app.serializers.custom_property as property_serializers
import plane.app.views.base as base_views
import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties

# The handlers are written once, as mixins over DRF's ModelViewSet, and served twice: under
# /api/ by the classes at the end of this module (session authentication) and under /api/v1/
# by plane.api.views.custom_property (API key authentication), which is what the Plane SDK and
# the stock MCP server call. Paths, request fields and response shapes are the SDK's.


class ProjectSettingsViewSetMixin:
    def get_permissions(self) -> t.List[api_permissions.BasePermission]:
        if self.request.method in api_permissions.SAFE_METHODS:
            return [app_permissions.ProjectLitePermission()]
        return [app_permissions.ProjectAdminPermission()]

    def get_serializer_context(self) -> t.Dict[str, t.Any]:
        return {**super().get_serializer_context(), **self.kwargs}


class IssueTypeViewSetMixin(ProjectSettingsViewSetMixin):
    serializer_class = property_serializers.IssueTypeSerializer

    def get_queryset(self) -> django_models.QuerySet[db_models.IssueType]:
        return (
            custom_properties.get_project_issue_types(self.kwargs["project_id"])
            .filter(workspace__slug=self.kwargs["slug"])
            .order_by("created_at")
        )

    def keep_one_default(self, issue_type: db_models.IssueType) -> None:
        if issue_type.is_default:
            self.get_queryset().exclude(pk=issue_type.pk).update(is_default=False)

    @django_transaction.atomic
    def perform_create(self, serializer: property_serializers.IssueTypeSerializer) -> None:
        project: db_models.Project = db_models.Project.objects.get(
            pk=self.kwargs["project_id"], workspace__slug=self.kwargs["slug"]
        )
        if not project.is_issue_type_enabled:
            raise api_exceptions.ValidationError({"error": "Work item types are not enabled for this project."})
        issue_type: db_models.IssueType = serializer.save(workspace_id=project.workspace_id)
        db_models.ProjectIssueType.objects.create(project=project, issue_type=issue_type)
        self.keep_one_default(issue_type)

    @django_transaction.atomic
    def perform_update(self, serializer: property_serializers.IssueTypeSerializer) -> None:
        self.keep_one_default(serializer.save())

    def perform_destroy(self, instance: db_models.IssueType) -> None:
        if instance.is_default:
            raise api_exceptions.ValidationError({"error": "The default type cannot be deleted."})
        # Only the link goes: the docs promise that work items keep a deleted type until
        # someone changes it, and deleting the type row would null their type.
        db_models.ProjectIssueType.objects.filter(project_id=self.kwargs["project_id"], issue_type=instance).delete()


class IssuePropertyViewSetMixin(ProjectSettingsViewSetMixin):
    serializer_class = property_serializers.IssuePropertySerializer

    def get_queryset(self) -> django_models.QuerySet[db_models.IssueProperty]:
        queryset: django_models.QuerySet[db_models.IssueProperty] = db_models.IssueProperty.objects.filter(
            workspace__slug=self.kwargs["slug"], project_id=self.kwargs["project_id"]
        ).prefetch_related("options")
        if "type_id" in self.kwargs:
            queryset = queryset.filter(issue_type_id=self.kwargs["type_id"])
        return queryset

    @django_transaction.atomic
    def perform_create(self, serializer: property_serializers.IssuePropertySerializer) -> None:
        issue_type: db_models.IssueType = custom_properties.get_project_issue_types(self.kwargs["project_id"]).get(
            pk=self.kwargs["type_id"]
        )
        options: property_serializers.IssuePropertyOptionSerializer = (
            property_serializers.IssuePropertyOptionSerializer(data=self.request.data.get("options", []), many=True)
        )
        options.is_valid(raise_exception=True)
        property: db_models.IssueProperty = serializer.save(project_id=self.kwargs["project_id"], issue_type=issue_type)
        options.save(project_id=property.project_id, property=property)

    @django_transaction.atomic
    def perform_update(self, serializer: property_serializers.IssuePropertySerializer) -> None:
        property: db_models.IssueProperty = serializer.save()
        if property.property_type == db_models.IssueProperty.PropertyType.CASCADING:
            custom_properties.delete_options_below_last_level(property)


class IssuePropertyOptionViewSetMixin(ProjectSettingsViewSetMixin):
    serializer_class = property_serializers.IssuePropertyOptionSerializer

    def get_queryset(self) -> django_models.QuerySet[db_models.IssuePropertyOption]:
        return db_models.IssuePropertyOption.objects.filter(
            workspace__slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            property_id=self.kwargs["property_id"],
        )

    def keep_one_default(self, option: db_models.IssuePropertyOption) -> None:
        if option.is_default and not option.property.is_multi:
            self.get_queryset().exclude(pk=option.pk).update(is_default=False)

    @django_transaction.atomic
    def perform_create(self, serializer: property_serializers.IssuePropertyOptionSerializer) -> None:
        property: db_models.IssueProperty = db_models.IssueProperty.objects.get(
            workspace__slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            pk=self.kwargs["property_id"],
            property_type__in=(
                db_models.IssueProperty.PropertyType.OPTION,
                db_models.IssueProperty.PropertyType.CASCADING,
            ),
        )
        self.keep_one_default(serializer.save(project_id=property.project_id, property=property))

    @django_transaction.atomic
    def perform_update(self, serializer: property_serializers.IssuePropertyOptionSerializer) -> None:
        option: db_models.IssuePropertyOption = serializer.instance
        if serializer.validated_data.get("parent", option.parent) != option.parent:
            # Work items chose the option under the option it moves away from, so they lose it
            # as they lose a deleted option.
            custom_properties.remove_option_from_work_items(option)
        self.keep_one_default(serializer.save())

    def retrieve(self, request: api_request.Request, *args: t.Any, **kwargs: t.Any) -> api_response.Response:
        option: db_models.IssuePropertyOption = self.get_object()
        # Deleting an option moves it out of the work items that selected it; the web asks
        # the user to confirm when this count is not zero.
        work_item_count: int = custom_properties.get_work_items_using_option(db_models.Issue, option).count()
        return api_response.Response({**self.get_serializer(option).data, "work_item_count": work_item_count})

    @django_transaction.atomic
    def perform_destroy(self, instance: db_models.IssuePropertyOption) -> None:
        custom_properties.remove_option_from_work_items(instance)
        custom_properties.delete_option(instance)


class IssueTypeViewSet(IssueTypeViewSetMixin, base_views.BaseViewSet):
    pass


class IssuePropertyViewSet(IssuePropertyViewSetMixin, base_views.BaseViewSet):
    pass


class IssuePropertyOptionViewSet(IssuePropertyOptionViewSetMixin, base_views.BaseViewSet):
    pass
