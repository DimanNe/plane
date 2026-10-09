# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.urls as django_urls

import plane.app.views.custom_property as custom_property_views

DETAIL_ACTIONS: t.Dict[str, str] = {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}

urlpatterns: t.List[django_urls.URLPattern] = [
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/",
        custom_property_views.IssueTypeViewSet.as_view({"get": "list", "post": "create"}),
        name="work-item-types",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:pk>/",
        custom_property_views.IssueTypeViewSet.as_view(DETAIL_ACTIONS),
        name="work-item-types",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:type_id>/work-item-properties/",
        custom_property_views.IssuePropertyViewSet.as_view({"get": "list", "post": "create"}),
        name="work-item-type-properties",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:type_id>/work-item-properties/<uuid:pk>/",
        custom_property_views.IssuePropertyViewSet.as_view(DETAIL_ACTIONS),
        name="work-item-type-properties",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/",
        custom_property_views.IssuePropertyViewSet.as_view({"get": "list"}),
        name="work-item-properties",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/<uuid:pk>/",
        custom_property_views.IssuePropertyViewSet.as_view(DETAIL_ACTIONS),
        name="work-item-properties",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/<uuid:property_id>/options/",
        custom_property_views.IssuePropertyOptionViewSet.as_view({"get": "list", "post": "create"}),
        name="work-item-property-options",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/<uuid:property_id>/options/<uuid:pk>/",
        custom_property_views.IssuePropertyOptionViewSet.as_view(DETAIL_ACTIONS),
        name="work-item-property-options",
    ),
]
