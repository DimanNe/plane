# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.urls as django_urls

import plane.api.views as api_views

urlpatterns: t.List[django_urls.URLPattern] = [
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/milestones/",
        api_views.MilestoneAPIViewSet.as_view({"get": "list", "post": "create"}),
        name="milestones",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/milestones/<uuid:pk>/",
        api_views.MilestoneAPIViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="milestones",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/milestones/<uuid:milestone_id>/work-items/",
        api_views.MilestoneAPIViewSet.as_view(
            {"get": "list_work_items", "post": "add_work_items", "delete": "remove_work_items"}
        ),
        name="milestone-work-items",
    ),
]
