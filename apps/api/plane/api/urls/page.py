# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.urls as django_urls

import plane.api.views.page as page_views

urlpatterns: t.List[django_urls.URLPattern] = [
    django_urls.path(
        "workspaces/<str:slug>/pages/",
        page_views.PageAPIViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-pages",
    ),
    django_urls.path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/",
        page_views.PageAPIViewSet.as_view({"get": "retrieve", "put": "partial_update", "delete": "destroy"}),
        name="workspace-pages",
    ),
    django_urls.path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/archive/",
        page_views.PageAPIViewSet.as_view({"post": "archive", "delete": "unarchive"}),
        name="workspace-page-archive-unarchive",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/",
        page_views.PageAPIViewSet.as_view({"get": "list", "post": "create"}),
        name="project-pages",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/",
        page_views.PageAPIViewSet.as_view({"get": "retrieve", "put": "partial_update", "delete": "destroy"}),
        name="project-pages",
    ),
    django_urls.path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/archive/",
        page_views.PageAPIViewSet.as_view({"post": "archive", "delete": "unarchive"}),
        name="project-page-archive-unarchive",
    ),
    django_urls.path(
        "workspaces/<str:slug>/collections/",
        page_views.CollectionAPIViewSet.as_view({"get": "list", "post": "create"}),
        name="collections",
    ),
    django_urls.path(
        "workspaces/<str:slug>/collections/<uuid:collection_id>/",
        page_views.CollectionAPIViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="collections",
    ),
    django_urls.path(
        "workspaces/<str:slug>/collections/<uuid:collection_id>/pages/",
        page_views.CollectionAPIViewSet.as_view({"get": "list_pages", "post": "add_pages"}),
        name="collection-pages",
    ),
    django_urls.path(
        "workspaces/<str:slug>/collections/<uuid:collection_id>/pages-search/",
        page_views.CollectionAPIViewSet.as_view({"get": "search_pages"}),
        name="collection-pages-search",
    ),
    django_urls.path(
        "workspaces/<str:slug>/collections/<uuid:collection_id>/pages/<uuid:page_collection_id>/",
        page_views.CollectionAPIViewSet.as_view({"patch": "update_page", "delete": "remove_page"}),
        name="collection-pages",
    ),
]
