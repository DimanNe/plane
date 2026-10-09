# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.urls as django_urls

import plane.api.views as api_views

urlpatterns: t.List[django_urls.URLPattern] = [
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/dependencies/",
        api_views.WorkItemDependencyListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="work-item-dependency-list",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/dependencies/"
        "<uuid:related_issue_id>/",
        api_views.WorkItemDependencyDetailAPIEndpoint.as_view(http_method_names=["delete"]),
        name="work-item-dependency-detail",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/work-item-relations/",
        api_views.WorkItemRelationListAPIEndpoint.as_view(http_method_names=["get"]),
        name="work-item-relation-list",
    ),
    django_urls.path(
        "workspaces/<str:slug>/work-item-relation-definitions/",
        api_views.WorkItemRelationDefinitionListAPIEndpoint.as_view(http_method_names=["get"]),
        name="work-item-relation-definition-list",
    ),
]
