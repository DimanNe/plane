# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import rest_framework.request as api_request
import rest_framework.response as api_response

import plane.api.serializers.feature as feature_serializers
import plane.api.views.base as base_views
import plane.app.permissions as app_permissions
import plane.db.models as db_models


class ProjectFeatureAPIEndpoint(base_views.BaseAPIView):
    permission_classes = [app_permissions.ProjectBasePermission]

    def get(self, request: api_request.Request, slug: str, project_id: uuid.UUID) -> api_response.Response:
        project: db_models.Project = db_models.Project.objects.get(pk=project_id, workspace__slug=slug)
        return api_response.Response(feature_serializers.ProjectFeatureSerializer(project).data)

    def patch(self, request: api_request.Request, slug: str, project_id: uuid.UUID) -> api_response.Response:
        project: db_models.Project = db_models.Project.objects.get(pk=project_id, workspace__slug=slug)
        serializer: feature_serializers.ProjectFeatureSerializer = feature_serializers.ProjectFeatureSerializer(
            project, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if project.intake_view and not db_models.Intake.objects.filter(project=project, is_default=True).exists():
            db_models.Intake.objects.create(name=f"{project.name} Intake", project=project, is_default=True)
        return api_response.Response(serializer.data)


class WorkspaceFeatureAPIEndpoint(base_views.BaseAPIView):
    permission_classes = [app_permissions.WorkSpaceBasePermission]

    def get(self, request: api_request.Request, slug: str) -> api_response.Response:
        workspace: db_models.Workspace = db_models.Workspace.objects.get(slug=slug)
        return api_response.Response(feature_serializers.WorkspaceFeatureSerializer(workspace).data)

    def patch(self, request: api_request.Request, slug: str) -> api_response.Response:
        workspace: db_models.Workspace = db_models.Workspace.objects.get(slug=slug)
        serializer: feature_serializers.WorkspaceFeatureSerializer = feature_serializers.WorkspaceFeatureSerializer(
            workspace, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response.Response(serializer.data)
