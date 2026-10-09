# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path


from plane.app.views import (
    PageViewSet,
    PageFavoriteViewSet,
    PagesDescriptionViewSet,
    PageVersionEndpoint,
    PageDuplicateEndpoint,
)
from plane.app.views.page.wiki import WorkspacePageViewSet, CollectionViewSet

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages-summary/",
        PageViewSet.as_view({"get": "summary"}),
        name="project-pages-summary",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/",
        PageViewSet.as_view({"get": "list", "post": "create"}),
        name="project-pages",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/",
        PageViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-pages",
    ),
    # favorite pages
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/favorite-pages/<uuid:page_id>/",
        PageFavoriteViewSet.as_view({"post": "create", "delete": "destroy"}),
        name="user-favorite-pages",
    ),
    # archived pages
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/archive/",
        PageViewSet.as_view({"post": "archive", "delete": "unarchive"}),
        name="project-page-archive-unarchive",
    ),
    # lock and unlock
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/lock/",
        PageViewSet.as_view({"post": "lock", "delete": "unlock"}),
        name="project-pages-lock-unlock",
    ),
    # private and public page
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/access/",
        PageViewSet.as_view({"post": "access"}),
        name="project-pages-access",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/description/",
        PagesDescriptionViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="page-description",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/versions/",
        PageVersionEndpoint.as_view(),
        name="page-versions",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/versions/<uuid:pk>/",
        PageVersionEndpoint.as_view(),
        name="page-versions",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/duplicate/",
        PageDuplicateEndpoint.as_view(),
        name="page-duplicate",
    ),
    # workspace pages (wiki)
    path(
        "workspaces/<str:slug>/pages/",
        WorkspacePageViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-pages",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/",
        WorkspacePageViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="workspace-pages",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/archive/",
        WorkspacePageViewSet.as_view({"post": "archive", "delete": "unarchive"}),
        name="workspace-page-archive-unarchive",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/lock/",
        WorkspacePageViewSet.as_view({"post": "lock", "delete": "unlock"}),
        name="workspace-pages-lock-unlock",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/description/",
        WorkspacePageViewSet.as_view({"get": "retrieve_description", "patch": "update_description"}),
        name="workspace-page-description",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/versions/",
        WorkspacePageViewSet.as_view({"get": "list_versions"}),
        name="workspace-page-versions",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/versions/<uuid:pk>/",
        WorkspacePageViewSet.as_view({"get": "retrieve_version"}),
        name="workspace-page-versions",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/duplicate/",
        WorkspacePageViewSet.as_view({"post": "duplicate"}),
        name="workspace-page-duplicate",
    ),
    # collections of workspace pages
    path(
        "workspaces/<str:slug>/collections/",
        CollectionViewSet.as_view({"get": "list", "post": "create"}),
        name="collections",
    ),
    path(
        "workspaces/<str:slug>/collections/<uuid:collection_id>/",
        CollectionViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="collections",
    ),
    path(
        "workspaces/<str:slug>/collections/<uuid:collection_id>/pages/",
        CollectionViewSet.as_view({"get": "list_pages", "post": "add_pages"}),
        name="collection-pages",
    ),
    path(
        "workspaces/<str:slug>/collections/<uuid:collection_id>/pages-search/",
        CollectionViewSet.as_view({"get": "search_pages"}),
        name="collection-pages-search",
    ),
    path(
        "workspaces/<str:slug>/collections/<uuid:collection_id>/pages/<uuid:page_collection_id>/",
        CollectionViewSet.as_view({"patch": "update_page", "delete": "remove_page"}),
        name="collection-pages",
    ),
]
