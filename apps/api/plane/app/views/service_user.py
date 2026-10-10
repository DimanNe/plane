# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import django.db.transaction as django_transaction
import rest_framework.request as api_request
import rest_framework.response as api_response
import rest_framework.serializers as api_serializers
import rest_framework.status as api_status

import plane.app.permissions as app_permissions
import plane.app.serializers as app_serializers
import plane.app.views.base as base_views
import plane.db.models as db_models
import plane.utils.service_users as service_users


class ServiceUserNameSerializer(api_serializers.Serializer):
    name = api_serializers.CharField(max_length=db_models.User._meta.get_field("display_name").max_length)


class WorkspaceMemberSerializer(app_serializers.WorkSpaceMemberSerializer):
    class Meta(app_serializers.WorkSpaceMemberSerializer.Meta):
        fields = ("id", "member", "role", "is_active", "created_at")


class ServiceUserEndpoint(base_views.BaseAPIView):
    # a member of the project may; a guest may not
    permission_classes = [app_permissions.ProjectEntityPermission]

    def post(self, request: api_request.Request, slug: str, project_id: uuid.UUID) -> api_response.Response:
        """Makes the service user with the given name a member of the project: the one the workspace has by
        that name, or a new one. Answers with what the lists of the workspace's and of the project's members
        give of it and a page keeps, so the page can add the member to what it holds without asking for the
        lists again; 201 when the user was created."""
        serializer: ServiceUserNameSerializer = ServiceUserNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project: db_models.Project = db_models.Project.objects.get(pk=project_id, workspace__slug=slug)
        workspace_member: db_models.WorkspaceMember
        project_member: db_models.ProjectMember
        is_created: bool
        with django_transaction.atomic():
            workspace_member, project_member, is_created = service_users.add_service_user_to_project(
                project, serializer.validated_data["name"]
            )
        return api_response.Response(
            {
                "workspace_member": WorkspaceMemberSerializer(workspace_member).data,
                "project_member": app_serializers.ProjectMemberRoleSerializer(project_member).data,
            },
            status=api_status.HTTP_201_CREATED if is_created else api_status.HTTP_200_OK,
        )
