# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.urls as django_urls

import plane.api.views as api_views

urlpatterns: t.List[django_urls.URLPattern] = [
    django_urls.path(
        "workspaces/<str:slug>/features/",
        api_views.WorkspaceFeatureAPIEndpoint.as_view(http_method_names=["get", "patch"]),
        name="workspace-features",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/features/",
        api_views.ProjectFeatureAPIEndpoint.as_view(http_method_names=["get", "patch"]),
        name="project-features",
    ),
]
