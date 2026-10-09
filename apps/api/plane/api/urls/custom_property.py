# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.urls as django_urls

import plane.api.views.custom_property as custom_property_views

DETAIL_ACTIONS: t.Dict[str, str] = {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}

urlpatterns: t.List[django_urls.URLPattern] = [
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/",
        custom_property_views.IssueTypeAPIEndpoint.as_view({"get": "list", "post": "create"}),
        name="work-item-types",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:pk>/",
        custom_property_views.IssueTypeAPIEndpoint.as_view(DETAIL_ACTIONS),
        name="work-item-types",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:type_id>/work-item-properties/",
        custom_property_views.IssuePropertyAPIEndpoint.as_view({"get": "list", "post": "create"}),
        name="work-item-type-properties",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:type_id>/work-item-properties/<uuid:pk>/",
        custom_property_views.IssuePropertyAPIEndpoint.as_view(DETAIL_ACTIONS),
        name="work-item-type-properties",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/",
        custom_property_views.IssuePropertyAPIEndpoint.as_view({"get": "list"}),
        name="work-item-properties",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/<uuid:pk>/",
        custom_property_views.IssuePropertyAPIEndpoint.as_view(DETAIL_ACTIONS),
        name="work-item-properties",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/<uuid:property_id>/options/",
        custom_property_views.IssuePropertyOptionAPIEndpoint.as_view({"get": "list", "post": "create"}),
        name="work-item-property-options",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/<uuid:property_id>/options/<uuid:pk>/",
        custom_property_views.IssuePropertyOptionAPIEndpoint.as_view(DETAIL_ACTIONS),
        name="work-item-property-options",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>"
        "/work-item-properties/<uuid:property_id>/values/",
        custom_property_views.IssuePropertyValueAPIEndpoint.as_view(
            {"get": "retrieve", "post": "update", "patch": "update", "delete": "destroy"}
        ),
        name="work-item-property-values",
    ),
]
