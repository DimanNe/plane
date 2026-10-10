# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.urls as django_urls

import plane.app.views.service_user as service_user_views

urlpatterns: t.List[django_urls.URLPattern] = [
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/service-users/",
        service_user_views.ServiceUserEndpoint.as_view(),
        name="project-service-users",
    ),
]
