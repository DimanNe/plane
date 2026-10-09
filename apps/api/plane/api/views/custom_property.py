# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import typing as t

import django.db.transaction as django_transaction
import django.utils.html as django_html
import django.utils.timezone as django_timezone
import rest_framework.exceptions as api_exceptions
import rest_framework.request as api_request
import rest_framework.response as api_response
import rest_framework.status as api_status

import plane.api.views.base as base_views
import plane.app.permissions as app_permissions
import plane.app.views.custom_property as custom_property_views
import plane.bgtasks.issue_activities_task as issue_activities_task
import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties
import plane.utils.property_formula as property_formula


class IssueTypeAPIEndpoint(custom_property_views.IssueTypeViewSetMixin, base_views.BaseViewSet):
    pass


class IssuePropertyAPIEndpoint(custom_property_views.IssuePropertyViewSetMixin, base_views.BaseViewSet):
    pass


class IssuePropertyOptionAPIEndpoint(custom_property_views.IssuePropertyOptionViewSetMixin, base_views.BaseViewSet):
    pass


class IssuePropertyValueAPIEndpoint(base_views.BaseViewSet):
    """
    One property of one work item, in the shape of the SDK's WorkItemPropertyValueDetail.

    The web writes values with the work item itself (`custom_properties` of the issue endpoints).
    The SDK has no such field and sets them here, one property per request, so this endpoint
    exists under /api/v1/ only.
    """

    permission_classes = [app_permissions.ProjectEntityPermission]

    def get_issue_and_property(self) -> t.Tuple[db_models.Issue, db_models.IssueProperty]:
        issue: db_models.Issue = db_models.Issue.objects.get(
            workspace__slug=self.kwargs["slug"], project_id=self.kwargs["project_id"], pk=self.kwargs["issue_id"]
        )
        return issue, db_models.IssueProperty.objects.get(issue_type_id=issue.type_id, pk=self.kwargs["property_id"])

    def get_value_response(
        self, issue: db_models.Issue, property: db_models.IssueProperty, value: property_formula.JsonValue
    ) -> api_response.Response:
        detail: t.Dict[str, property_formula.JsonValue] = {
            # The SDK requires an id; a value has no row of its own, so it is the property's.
            "id": str(property.id),
            "property_id": str(property.id),
            "issue_id": str(issue.id),
            "value": value,
        }
        if property.relation_type == db_models.IssueProperty.RelationType.RICH_TEXT and value is not None:
            detail["value"] = None
            detail["value_detail"] = {
                "id": None,
                "description_html": value,
                "description_stripped": django_html.strip_tags(value),
            }
        if isinstance(value, list):
            return api_response.Response([{**detail, "value": item} for item in value])
        return api_response.Response(detail)

    def retrieve(self, request: api_request.Request, *args: t.Any, **kwargs: t.Any) -> api_response.Response:
        issue: db_models.Issue
        property: db_models.IssueProperty
        issue, property = self.get_issue_and_property()
        value: property_formula.JsonValue = {
            **issue.custom_properties,
            **custom_properties.get_formula_payload(
                custom_properties.get_type_properties(issue.type_id), issue.custom_properties
            )["formula_values"],
        }.get(str(property.id))
        if value is None:
            return api_response.Response(
                {"error": "The property has no value on this work item."}, status=api_status.HTTP_404_NOT_FOUND
            )
        return self.get_value_response(issue, property, value)

    def write_value(self, value: property_formula.JsonValue) -> api_response.Response:
        issue: db_models.Issue
        property: db_models.IssueProperty
        issue, property = self.get_issue_and_property()
        if property.relation_type == db_models.IssueProperty.RelationType.RICH_TEXT and value is not None:
            if not isinstance(value, dict):
                # The stock MCP server looks for this sentence to tell its caller what to send.
                raise api_exceptions.ValidationError(
                    {"error": "Rich text value must be an object with description_html."}
                )
            value = value.get("description_html")
        previous_values: custom_properties.PropertyValues = issue.custom_properties
        with django_transaction.atomic():
            issue.custom_properties = custom_properties.get_changes_for_update(
                issue, None, {str(property.id): value}, None, check_required=False
            )["custom_properties"]
            issue.save(update_fields=["custom_properties", "updated_at"])
        issue_activities_task.issue_activity.delay(
            type="issue.activity.updated",
            requested_data=json.dumps({"custom_properties": {str(property.id): value}}),
            actor_id=str(self.request.user.id),
            issue_id=str(issue.id),
            project_id=str(issue.project_id),
            current_instance=json.dumps({"custom_properties": previous_values}),
            epoch=int(django_timezone.now().timestamp()),
        )
        return self.get_value_response(issue, property, issue.custom_properties.get(str(property.id)))

    def update(self, request: api_request.Request, *args: t.Any, **kwargs: t.Any) -> api_response.Response:
        return self.write_value(request.data["value"])

    def destroy(self, request: api_request.Request, *args: t.Any, **kwargs: t.Any) -> api_response.Response:
        self.write_value(None)
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)
