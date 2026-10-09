# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64
import datetime
import json
import typing as t
import uuid

import django.conf as django_conf
import django.db.models as django_models
import django.http as django_http
import requests
import rest_framework.permissions as api_permissions
import rest_framework.request as api_request
import rest_framework.response as api_response
import rest_framework.status as api_status
import rest_framework.views as api_views

import plane.api.serializers.page as page_serializers
import plane.app.permissions as app_permissions
import plane.app.serializers as app_serializers
import plane.app.views.base as base_views
import plane.app.views.page.base as page_views
import plane.bgtasks.copy_s3_object as copy_s3_object
import plane.bgtasks.page_transaction_task as page_transaction_task
import plane.bgtasks.page_version_task as page_version_task
import plane.bgtasks.recent_visited_task as recent_visited_task
import plane.db.models as db_models
import plane.utils.error_codes as error_codes
import plane.utils.order_queryset as order_queryset
import plane.utils.page_tree as page_tree
import plane.utils.url as url_utils


class WikiPermission(api_permissions.BasePermission):
    """Workspace admins and members use the wiki while the workspace has it turned on."""

    def has_permission(self, request: api_request.Request, view: api_views.APIView) -> bool:
        return db_models.WorkspaceMember.objects.filter(
            workspace__slug=view.kwargs["slug"],
            workspace__is_wiki_enabled=True,
            member=request.user,
            role__in=[app_permissions.ROLE.ADMIN.value, app_permissions.ROLE.MEMBER.value],
            is_active=True,
        ).exists()


def get_pages(slug: str, user: db_models.User) -> django_models.QuerySet[db_models.Page]:
    return (
        db_models.Page.objects.filter(workspace__slug=slug)
        .filter(django_models.Q(owned_by=user) | django_models.Q(access=db_models.Page.PUBLIC_ACCESS))
        .annotate(
            is_favorite=django_models.Exists(
                db_models.UserFavorite.objects.filter(
                    user=user, entity_type="page", entity_identifier=django_models.OuterRef("pk")
                )
            )
        )
    )


def get_collections(slug: str, user: db_models.User) -> django_models.QuerySet[db_models.Collection]:
    return db_models.Collection.objects.filter(workspace__slug=slug).filter(
        django_models.Q(owned_by=user) | django_models.Q(access=db_models.Page.PUBLIC_ACCESS)
    )


class PageViewSetMixin:
    """
    Pages of the workspace (the wiki), or of a project when the route names one, for the web app
    and for /api/v1/.
    """

    # The web app and the live server write the names and descriptions the editor already holds.
    # Any other writer changes them behind the editor, so the collaborative document must take the
    # change as well, or the next save of an open editor would undo it.
    writes_bypass_editor: bool = False

    def get_permissions(self) -> t.List[api_permissions.BasePermission]:
        if "project_id" in self.kwargs:
            return [app_permissions.ProjectPagePermission()]
        return [api_permissions.IsAuthenticated(), WikiPermission()]

    def get_queryset(self) -> django_models.QuerySet[db_models.Page]:
        pages: django_models.QuerySet[db_models.Page] = get_pages(self.kwargs["slug"], self.request.user)
        if "project_id" not in self.kwargs:
            return pages.filter(is_global=True)
        pages = pages.filter(
            project_pages__project_id=self.kwargs["project_id"], project_pages__deleted_at__isnull=True
        )
        if db_models.ProjectMember.objects.filter(
            project_id=self.kwargs["project_id"],
            project__guest_view_all_features=False,
            member=self.request.user,
            role=app_permissions.ROLE.GUEST.value,
            is_active=True,
        ).exists():
            pages = pages.filter(owned_by=self.request.user)
        return pages

    def is_page_owner_or_admin(self, page: db_models.Page) -> bool:
        members: django_models.QuerySet[t.Union[db_models.ProjectMember, db_models.WorkspaceMember]] = (
            db_models.ProjectMember.objects.filter(project_id=self.kwargs["project_id"])
            if "project_id" in self.kwargs
            else db_models.WorkspaceMember.objects.filter(workspace__slug=self.kwargs["slug"])
        )
        return (
            page.owned_by_id == self.request.user.id
            or members.filter(member=self.request.user, role=app_permissions.ROLE.ADMIN.value, is_active=True).exists()
        )

    def get_next_sort_order(self) -> float:
        largest: t.Optional[float] = self.get_queryset().aggregate(largest=django_models.Max("sort_order"))["largest"]
        return (largest or 0) + db_models.Page.DEFAULT_SORT_ORDER

    def save_document(self, page: db_models.Page, document: t.Dict[str, t.Any]) -> None:
        """Stores the document of the page as an editor holds it: its binary, HTML and JSON, and its title."""
        old_description_html: str = page.description_html
        serializer: app_serializers.PageBinaryUpdateSerializer = app_serializers.PageBinaryUpdateSerializer(
            page, data=document, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.queue_description_tasks(page, old_description_html)

    def queue_description_tasks(self, page: db_models.Page, old_description_html: str) -> None:
        if page.description_html == old_description_html:
            return
        page_transaction_task.page_transaction.delay(
            new_description_html=page.description_html,
            old_description_html=old_description_html,
            page_id=page.id,
        )
        page_version_task.track_page_version.delay(
            page_id=page.id,
            existing_instance=json.dumps({"description_html": old_description_html}),
            user_id=self.request.user.id,
        )

    def list(
        self, request: api_request.Request, slug: str, project_id: t.Optional[uuid.UUID] = None
    ) -> api_response.Response:
        pages: django_models.QuerySet[db_models.Page] = self.get_queryset()
        if "parent_id" in request.GET:
            pages = pages.filter(parent_id=request.GET["parent_id"])
        if "created_by" in request.GET:
            pages = pages.filter(created_by_id__in=request.GET["created_by"].split(","))
        return self.paginate(
            request=request,
            queryset=pages,
            order_by=order_queryset.sanitize_order_by(
                request.GET.get("order_by"), order_queryset.PAGE_ORDER_BY_ALLOWLIST, default="sort_order"
            ),
            on_results=lambda results: page_serializers.PageSerializer(results, many=True).data,
        )

    def retrieve(
        self, request: api_request.Request, slug: str, page_id: uuid.UUID, project_id: t.Optional[uuid.UUID] = None
    ) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        if request.GET.get("track_visit") == "true":
            recent_visited_task.recent_visited_task.delay(
                slug=slug,
                entity_name="page",
                entity_identifier=page_id,
                user_id=request.user.id,
                project_id=project_id,
            )
        return api_response.Response(page_serializers.PageDetailSerializer(page).data)

    def create(
        self, request: api_request.Request, slug: str, project_id: t.Optional[uuid.UUID] = None
    ) -> api_response.Response:
        serializer: page_serializers.PageDetailSerializer = page_serializers.PageDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent_id: t.Optional[uuid.UUID] = serializer.validated_data.pop("parent_id", None)
        collection_id: t.Optional[uuid.UUID] = serializer.validated_data.pop("collection_id", None)
        parent: t.Optional[db_models.Page] = self.get_queryset().get(pk=parent_id) if parent_id else None
        collection: t.Optional[db_models.Collection] = (
            get_collections(slug, request.user).get(pk=collection_id) if collection_id and not project_id else None
        )
        if parent and (parent.archived_at or (collection and collection.id != parent.collection_id)):
            return api_response.Response(
                {"error": "A page is nested under a page that is not archived and takes the collection of that page"},
                status=api_status.HTTP_400_BAD_REQUEST,
            )
        if "sort_order" not in serializer.validated_data:
            serializer.validated_data["sort_order"] = self.get_next_sort_order()
        workspace: db_models.Workspace = db_models.Workspace.objects.get(slug=slug)
        page: db_models.Page = serializer.save(workspace=workspace, owned_by=request.user, is_global=project_id is None)
        if project_id:
            db_models.ProjectPage.objects.create(workspace=workspace, project_id=project_id, page=page)
        page_tree.place_page(page, parent, collection)
        page_transaction_task.page_transaction.delay(
            new_description_html=page.description_html, old_description_html=None, page_id=page.id
        )
        return api_response.Response(
            page_serializers.PageDetailSerializer(self.get_queryset().get(pk=page.id)).data,
            status=api_status.HTTP_201_CREATED,
        )

    def partial_update(
        self, request: api_request.Request, slug: str, page_id: uuid.UUID, project_id: t.Optional[uuid.UUID] = None
    ) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        serializer: page_serializers.PageDetailSerializer = page_serializers.PageDetailSerializer(
            page, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        data: t.Dict[str, t.Any] = serializer.validated_data
        # A locked page takes only an update that unlocks it.
        if page.archived_at or (page.is_locked and data.get("is_locked", True)):
            return api_response.Response(
                {"error": "Page is archived" if page.archived_at else "Page is locked"},
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        access: int = data.get("access", page.access)
        is_placed: bool = "parent_id" in data or "collection_id" in data or access != page.access
        if is_placed:
            parent: t.Optional[db_models.Page] = page.parent
            if "parent_id" in data:
                parent = self.get_queryset().get(pk=data["parent_id"]) if data["parent_id"] else None
            if parent and (
                parent.archived_at
                or parent.id == page.id
                or parent.id in page_tree.get_nested_page_ids(page.id)
                or data.get("access", parent.access) != parent.access
                or data.get("collection_id", parent.collection_id) != parent.collection_id
            ):
                return api_response.Response(
                    {
                        "error": "A page is nested under a page that is not archived and not nested under it, "
                        "and takes the access and the collection of that page"
                    },
                    status=api_status.HTTP_400_BAD_REQUEST,
                )
            collection: t.Optional[db_models.Collection] = page.collection
            if "collection_id" in data and not project_id:
                collection = (
                    get_collections(slug, request.user).get(pk=data["collection_id"]) if data["collection_id"] else None
                )
            elif collection and collection.access != access:
                collection = None
            # A nested page takes the access of its parent, a page in a collection the access of the collection.
            access = parent.access if parent else collection.access if collection else access
            if access != page.access and page.owned_by_id != request.user.id:
                return api_response.Response(
                    {"error": "Access cannot be updated since this page is owned by someone else"},
                    status=api_status.HTTP_400_BAD_REQUEST,
                )
            page.access = access
        key: str
        for key in ("parent_id", "collection_id", "access"):
            data.pop(key, None)

        document: t.Optional[t.Dict[str, t.Any]] = None
        if self.writes_bypass_editor and page.description_binary and ("name" in data or "description_html" in data):
            try:
                live_response: requests.Response = requests.post(
                    url_utils.normalize_url_path(f"{django_conf.settings.LIVE_URL}/page-content/"),
                    json={
                        "page_id": str(page.id),
                        "description_binary": base64.b64encode(page.description_binary).decode(),
                        "name": data.get("name"),
                        "description_html": data.pop("description_html", None),
                    },
                    headers={"live-server-secret-key": django_conf.settings.LIVE_SERVER_SECRET_KEY},
                    timeout=20,
                )
                live_response.raise_for_status()
                document = live_response.json()
            except requests.RequestException:
                return api_response.Response(
                    {"error": "The live server did not take the change. Nothing is written."},
                    status=api_status.HTTP_502_BAD_GATEWAY,
                )

        old_description_html: str = page.description_html
        # with the description of a page no editor has opened: it has no document to keep in step
        serializer.save()
        if is_placed:
            page_tree.place_page(page, parent, collection)
        if document:
            self.save_document(page, document)
        else:
            self.queue_description_tasks(page, old_description_html)
        return api_response.Response(page_serializers.PageDetailSerializer(self.get_queryset().get(pk=page_id)).data)

    def archive(
        self, request: api_request.Request, slug: str, page_id: uuid.UUID, project_id: t.Optional[uuid.UUID] = None
    ) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        if not self.is_page_owner_or_admin(page):
            return api_response.Response(
                {"error": "Only the owner or admin can archive the page"}, status=api_status.HTTP_400_BAD_REQUEST
            )
        db_models.UserFavorite.objects.filter(
            entity_type="page", entity_identifier__in=[page.id, *page_tree.get_nested_page_ids(page.id)]
        ).delete()
        page_views.unarchive_archive_page_and_descendants(page_id, datetime.datetime.now())
        return api_response.Response({"archived_at": str(datetime.datetime.now())})

    def unarchive(
        self, request: api_request.Request, slug: str, page_id: uuid.UUID, project_id: t.Optional[uuid.UUID] = None
    ) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        if not self.is_page_owner_or_admin(page):
            return api_response.Response(
                {"error": "Only the owner or admin can un archive the page"}, status=api_status.HTTP_400_BAD_REQUEST
            )
        if page.parent_id and page.parent.archived_at:
            return api_response.Response(
                {"error": "Restore the parent page first"}, status=api_status.HTTP_400_BAD_REQUEST
            )
        page_views.unarchive_archive_page_and_descendants(page_id, None)
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)

    def destroy(
        self, request: api_request.Request, slug: str, page_id: uuid.UUID, project_id: t.Optional[uuid.UUID] = None
    ) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        if page.archived_at is None:
            return api_response.Response(
                {"error": "The page should be archived before deleting"}, status=api_status.HTTP_400_BAD_REQUEST
            )
        if not self.is_page_owner_or_admin(page):
            return api_response.Response(
                {"error": "Only admin or owner can delete the page"}, status=api_status.HTTP_403_FORBIDDEN
            )
        nested_pages: django_models.QuerySet[db_models.Page] = db_models.Page.objects.filter(
            id__in=page_tree.get_nested_page_ids(page.id)
        )
        deleted_ids: t.List[uuid.UUID] = [page.id]
        if project_id:
            # The pages nested under a project page stay, as top level archived pages.
            nested_pages.filter(parent=page).update(parent=None)
        else:
            deleted_ids.extend(nested_pages.values_list("id", flat=True))
            nested_pages.delete()
        page.delete()
        db_models.UserFavorite.objects.filter(entity_type="page", entity_identifier__in=deleted_ids).delete()
        db_models.UserRecentVisit.objects.filter(entity_name="page", entity_identifier__in=deleted_ids).delete(
            soft=False
        )
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)


class WorkspacePageViewSet(PageViewSetMixin, base_views.BaseViewSet):
    """What the web app and the live server need of a wiki page beyond PageViewSetMixin."""

    def lock(self, request: api_request.Request, slug: str, page_id: uuid.UUID) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        nested_page_ids: t.List[uuid.UUID] = (
            page_tree.get_nested_page_ids(page.id) if request.data.get("recursive") else []
        )
        db_models.Page.objects.filter(id__in=[page.id, *nested_page_ids]).update(is_locked=True)
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)

    def unlock(self, request: api_request.Request, slug: str, page_id: uuid.UUID) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        nested_page_ids: t.List[uuid.UUID] = (
            page_tree.get_nested_page_ids(page.id) if request.data.get("recursive") else []
        )
        db_models.Page.objects.filter(id__in=[page.id, *nested_page_ids]).update(is_locked=False)
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)

    def retrieve_description(
        self, request: api_request.Request, slug: str, page_id: uuid.UUID
    ) -> django_http.HttpResponse:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        return django_http.HttpResponse(
            bytes(page.description_binary or b""),
            content_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="page_description.bin"'},
        )

    def update_description(self, request: api_request.Request, slug: str, page_id: uuid.UUID) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        if page.is_locked or page.archived_at:
            error: str = "PAGE_LOCKED" if page.is_locked else "PAGE_ARCHIVED"
            return api_response.Response(
                {"error_code": error_codes.ERROR_CODES[error], "error_message": error},
                status=api_status.HTTP_400_BAD_REQUEST,
            )
        self.save_document(page, request.data)
        return api_response.Response({"message": "Updated successfully"})

    def list_versions(self, request: api_request.Request, slug: str, page_id: uuid.UUID) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        return api_response.Response(
            app_serializers.PageVersionSerializer(db_models.PageVersion.objects.filter(page=page), many=True).data
        )

    def retrieve_version(
        self, request: api_request.Request, slug: str, page_id: uuid.UUID, pk: uuid.UUID
    ) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        return api_response.Response(
            app_serializers.PageVersionDetailSerializer(db_models.PageVersion.objects.get(page=page, pk=pk)).data
        )

    def duplicate(self, request: api_request.Request, slug: str, page_id: uuid.UUID) -> api_response.Response:
        page: db_models.Page = self.get_queryset().get(pk=page_id)
        page.pk = None
        page.name = f"{page.name} (Copy)"
        page.sort_order = self.get_next_sort_order()
        page.description_binary = None
        page.owned_by = request.user
        page.created_by = request.user
        page.save()
        page_transaction_task.page_transaction.delay(
            new_description_html=page.description_html, old_description_html=None, page_id=page.id
        )
        copy_s3_object.copy_s3_objects_of_description_and_assets.delay(
            entity_name="PAGE",
            entity_identifier=page.id,
            project_id=None,
            slug=slug,
            user_id=request.user.id,
        )
        return api_response.Response(
            page_serializers.PageDetailSerializer(self.get_queryset().get(pk=page.id)).data,
            status=api_status.HTTP_201_CREATED,
        )


class CollectionViewSetMixin:
    """Collections of wiki pages, for the web app and for /api/v1/."""

    permission_classes: t.List[t.Type[api_permissions.BasePermission]] = [
        api_permissions.IsAuthenticated,
        WikiPermission,
    ]

    def get_queryset(self) -> django_models.QuerySet[db_models.Collection]:
        return get_collections(self.kwargs["slug"], self.request.user)

    def get_pages(self) -> django_models.QuerySet[db_models.Page]:
        return get_pages(self.kwargs["slug"], self.request.user).filter(is_global=True)

    def list(self, request: api_request.Request, slug: str) -> api_response.Response:
        return api_response.Response(page_serializers.CollectionSerializer(self.get_queryset(), many=True).data)

    def create(self, request: api_request.Request, slug: str) -> api_response.Response:
        serializer: page_serializers.CollectionSerializer = page_serializers.CollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if "sort_order" not in serializer.validated_data:
            # The default collection is created when a public page first needs it, with the default sort order:
            # the other collections of the workspace go after it.
            largest: t.Optional[float] = db_models.Collection.objects.filter(workspace__slug=slug).aggregate(
                largest=django_models.Max("sort_order")
            )["largest"]
            serializer.validated_data["sort_order"] = (
                largest or db_models.Page.DEFAULT_SORT_ORDER
            ) + db_models.Page.DEFAULT_SORT_ORDER
        serializer.save(workspace=db_models.Workspace.objects.get(slug=slug), owned_by=request.user)
        return api_response.Response(serializer.data, status=api_status.HTTP_201_CREATED)

    def retrieve(self, request: api_request.Request, slug: str, collection_id: uuid.UUID) -> api_response.Response:
        collection: db_models.Collection = self.get_queryset().get(pk=collection_id)
        return api_response.Response(page_serializers.CollectionSerializer(collection).data)

    def partial_update(
        self, request: api_request.Request, slug: str, collection_id: uuid.UUID
    ) -> api_response.Response:
        collection: db_models.Collection = self.get_queryset().get(pk=collection_id)
        serializer: page_serializers.CollectionSerializer = page_serializers.CollectionSerializer(
            collection, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response.Response(serializer.data)

    def destroy(self, request: api_request.Request, slug: str, collection_id: uuid.UUID) -> api_response.Response:
        collection: db_models.Collection = self.get_queryset().get(pk=collection_id)
        if collection.is_default:
            return api_response.Response(
                {"error": "The default collection cannot be deleted"}, status=api_status.HTTP_400_BAD_REQUEST
            )
        if (
            collection.owned_by_id != request.user.id
            and not db_models.WorkspaceMember.objects.filter(
                workspace__slug=slug, member=request.user, role=app_permissions.ROLE.ADMIN.value, is_active=True
            ).exists()
        ):
            return api_response.Response(
                {"error": "Only admin or owner can delete the collection"}, status=api_status.HTTP_403_FORBIDDEN
            )
        pages: django_models.QuerySet[db_models.Page] = db_models.Page.objects.filter(collection=collection)
        if collection.access == db_models.Page.PRIVATE_ACCESS or request.GET.get("archive_pages", "true") == "true":
            pages.filter(archived_at__isnull=True).update(archived_at=datetime.datetime.now())
        page: db_models.Page
        for page in pages.filter(parent__isnull=True):
            page_tree.place_page(page, None, None)
        collection.delete()
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)

    def list_pages(self, request: api_request.Request, slug: str, collection_id: uuid.UUID) -> api_response.Response:
        pages: django_models.QuerySet[db_models.Page] = self.get_pages().filter(
            collection=self.get_queryset().get(pk=collection_id), parent_id=request.GET.get("parent_id")
        )
        if "search" in request.GET:
            pages = pages.filter(name__icontains=request.GET["search"])
        return self.paginate(
            request=request,
            queryset=pages,
            order_by="sort_order",
            on_results=lambda results: page_serializers.CollectionBranchPageSerializer(results, many=True).data,
        )

    def search_pages(self, request: api_request.Request, slug: str, collection_id: uuid.UUID) -> api_response.Response:
        pages: django_models.QuerySet[db_models.Page] = (
            self.get_pages()
            .filter(parent__isnull=True, archived_at__isnull=True, name__icontains=request.GET.get("search", ""))
            .exclude(collection=self.get_queryset().get(pk=collection_id))
        )
        return api_response.Response(page_serializers.PageLiteSerializer(pages, many=True).data)

    def add_pages(self, request: api_request.Request, slug: str, collection_id: uuid.UUID) -> api_response.Response:
        collection: db_models.Collection = self.get_queryset().get(pk=collection_id)
        serializer: page_serializers.CollectionPageAddSerializer = page_serializers.CollectionPageAddSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        # Only its owner changes the access of a page.
        pages: t.List[db_models.Page] = list(
            self.get_pages()
            .filter(pk__in=serializer.validated_data["page_ids"], parent__isnull=True)
            .filter(django_models.Q(access=collection.access) | django_models.Q(owned_by=request.user))
        )
        page: db_models.Page
        for page in pages:
            page_tree.place_page(page, None, collection)
        return api_response.Response(
            page_serializers.CollectionPageSerializer(pages, many=True).data, status=api_status.HTTP_201_CREATED
        )

    def update_page(
        self, request: api_request.Request, slug: str, collection_id: uuid.UUID, page_collection_id: uuid.UUID
    ) -> api_response.Response:
        page: db_models.Page = self.get_pages().get(
            pk=page_collection_id, collection_id=collection_id, parent__isnull=True
        )
        serializer: page_serializers.CollectionPageUpdateSerializer = page_serializers.CollectionPageUpdateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        collection: db_models.Collection = self.get_queryset().get(
            pk=serializer.validated_data.get("collection", collection_id)
        )
        if collection.access != page.access and page.owned_by_id != request.user.id:
            return api_response.Response(
                {"error": "Access cannot be updated since this page is owned by someone else"},
                status=api_status.HTTP_400_BAD_REQUEST,
            )
        if "sort_order" in serializer.validated_data:
            page.sort_order = serializer.validated_data["sort_order"]
            page.save(update_fields=["sort_order", "updated_at", "updated_by"])
        page_tree.place_page(page, None, collection)
        return api_response.Response(page_serializers.CollectionPageSerializer(page).data)

    def remove_page(
        self, request: api_request.Request, slug: str, collection_id: uuid.UUID, page_collection_id: uuid.UUID
    ) -> api_response.Response:
        page: db_models.Page = self.get_pages().get(
            pk=page_collection_id, collection_id=collection_id, parent__isnull=True
        )
        page_tree.place_page(page, None, None)
        return api_response.Response(status=api_status.HTTP_204_NO_CONTENT)


class CollectionViewSet(CollectionViewSetMixin, base_views.BaseViewSet):
    pass
