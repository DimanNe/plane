/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { attachInstruction, extractInstruction } from "@atlaskit/pragmatic-drag-and-drop-hitbox/tree-item";
import { observer } from "mobx-react";
import Link from "next/link";
import { useParams } from "next/navigation";
// plane imports
import { EPageAccess, EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import {
  AddOutline,
  AddPageOutline,
  ChevronRightOutline,
  DeleteOutline,
  EditOutline,
  FolderLockOutline,
  FolderOutline,
  LinkPageOutline,
  MoreHorizontalOutline,
} from "@makeplane/propel/icons";
import { DropIndicator } from "@plane/blocks/common";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { InstructionType, TPage } from "@plane/types";
import { cn } from "@plane/utils";
// components
import { PageTreeNode } from "@/components/pages/nesting/page-tree";
import { SidebarNavItem } from "@/components/sidebar/sidebar-navigation";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { useUser, useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
// local imports
import { AddExistingPagesModal } from "./add-existing-pages-modal";
import { WikiCollectionModal } from "./collection-modal";
import { useMovePage } from "./move-page-provider";

const storeType = EPageStoreType.WORKSPACE;

// a collection goes above the collection it is dropped on, or below the last one
const getReorderInstruction = (dropTargetData: Record<string | symbol, unknown>): InstructionType =>
  extractInstruction(dropTargetData)?.type === "reorder-below" ? "reorder-below" : "reorder-above";

type Props = {
  collectionId: string;
  isLastChild: boolean;
  onCreatePage: (pageData: Partial<TPage>) => Promise<void>;
  onCreateNestedPage: (parentPageId: string) => void;
  onPageDrop: (pageId: string, targetPageId: string, instruction: InstructionType) => void;
};

export const WikiCollectionItem = observer(function WikiCollectionItem(props: Props) {
  const { collectionId, isLastChild, onCreatePage, onCreateNestedPage, onPageDrop } = props;
  // states
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMenuActive, setIsMenuActive] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAddPagesModalOpen, setIsAddPagesModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [instruction, setInstruction] = useState<InstructionType | undefined>(undefined);
  // refs
  const rowRef = useRef<HTMLDivElement>(null);
  // router
  const router = useAppRouter();
  const { workspaceSlug, collectionId: activeCollectionId, pageId: activePageId } = useParams();
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { data: currentUser } = useUser();
  const { allowPermissions } = useUserPermissions();
  const { getPageById, getCollectionById, getTopLevelPageIds, removeCollection, reorderCollection } =
    usePageStore(storeType);
  const movePage = useMovePage();
  // derived values
  const collection = getCollectionById(collectionId);
  const pageIds = getTopLevelPageIds(collectionId);
  const isActive = activeCollectionId === collectionId;
  const isActivePageInCollection = !!activePageId && getPageById(activePageId)?.collection_id === collectionId;
  const isPrivate = collection?.access === EPageAccess.PRIVATE;
  const errorTitle = t("toast.error");
  const reorderErrorMessage = t("wiki_collections.toasts.rename_error");
  const canManageCollection =
    collection?.owned_by_id === currentUser?.id ||
    allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);

  // the open collection, and the path to the open page, stay visible
  useEffect(() => {
    if (isActive || isActivePageInCollection) setIsExpanded(true);
  }, [isActive, isActivePageInCollection]);

  // a collection is dropped above or below another collection, a page into a collection
  useEffect(() => {
    const element = rowRef.current;
    if (!element) return;

    return combine(
      draggable({
        element,
        getInitialData: () => ({ collectionId }),
      }),
      dropTargetForElements({
        element,
        canDrop: ({ source }) => {
          if (typeof source.data.collectionId === "string") return source.data.collectionId !== collectionId;
          if (typeof source.data.pageId !== "string" || source.data.storeType !== storeType) return false;
          const page = getPageById(source.data.pageId);
          return !!page && (page.collection_id !== collectionId || !!page.parent_id);
        },
        getData: ({ input, element: targetElement }) =>
          attachInstruction(
            { collectionId },
            {
              input,
              element: targetElement,
              currentLevel: 0,
              indentPerLevel: 0,
              mode: "standard",
              block: isLastChild ? ["make-child"] : ["make-child", "reorder-below"],
            }
          ),
        onDrag: ({ self, source }) => {
          setInstruction(
            typeof source.data.collectionId === "string" ? getReorderInstruction(self.data) : "make-child"
          );
        },
        onDragLeave: () => {
          setInstruction(undefined);
        },
        onDrop: ({ self, source }) => {
          setInstruction(undefined);
          if (typeof source.data.collectionId === "string") {
            reorderCollection(source.data.collectionId, collectionId, getReorderInstruction(self.data)).catch(() =>
              setToast({ type: "error", title: errorTitle, message: reorderErrorMessage })
            );
          } else if (typeof source.data.pageId === "string") {
            movePage(source.data.pageId, { parent_id: null, collection_id: collectionId });
            setIsExpanded(true);
          }
        },
      })
    );
  }, [collectionId, errorTitle, getPageById, isLastChild, movePage, reorderCollection, reorderErrorMessage]);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await removeCollection(collectionId);
      setIsDeleteDialogOpen(false);
      setToast({
        type: "success",
        title: t("toast.success"),
        message: t("wiki_collections.toasts.deleted"),
      });
      if (isActive) router.push(`/${workspaceSlug}/wiki`);
    } catch {
      setToast({
        type: "error",
        title: errorTitle,
        message: t("wiki_collections.toasts.delete_error"),
      });
    } finally {
      setIsDeleting(false);
    }
  };

  if (!collection) return null;

  const CollectionIcon = isPrivate ? FolderLockOutline : FolderOutline;

  return (
    <>
      {isEditModalOpen && <WikiCollectionModal collection={collection} onClose={() => setIsEditModalOpen(false)} />}
      <AddExistingPagesModal
        collectionId={collectionId}
        isOpen={isAddPagesModalOpen}
        onClose={() => setIsAddPagesModalOpen(false)}
      />
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        handleClose={() => setIsDeleteDialogOpen(false)}
        handleSubmit={handleDelete}
        isSubmitting={isDeleting}
        title={t("wiki_collections.delete_modal.title")}
        content={t(
          isPrivate
            ? "wiki_collections.delete_modal.archive_pages_description"
            : "wiki_collections.delete_modal.keep_pages_description"
        )}
      />
      <div
        ref={rowRef}
        className={cn("relative", { "rounded-md bg-layer-transparent-hover": instruction === "make-child" })}
      >
        <DropIndicator classNames="absolute top-0" isVisible={instruction === "reorder-above"} />
        <SidebarNavItem isActive={isActive} className="gap-1">
          <div className="flex min-w-0 flex-grow items-center gap-1">
            <button
              type="button"
              className="grid size-4 flex-shrink-0 place-items-center rounded-sm text-placeholder hover:text-secondary"
              onClick={() => setIsExpanded(!isExpanded)}
              aria-expanded={isExpanded}
              aria-label={collection.name}
            >
              <ChevronRightOutline className={cn("size-3.5 transition-transform", { "rotate-90": isExpanded })} />
            </button>
            <Link
              href={`/${workspaceSlug}/wiki/collections/${collectionId}`}
              className="flex min-w-0 flex-grow items-center gap-1.5"
              draggable={false}
            >
              <span className="grid size-4 flex-shrink-0 place-items-center">
                {collection.logo_props?.in_use ? (
                  <Logo logo={collection.logo_props} size={14} type="lucide" />
                ) : (
                  <CollectionIcon className="size-3.5 text-tertiary" />
                )}
              </span>
              <span className="truncate text-13 leading-5 font-medium">{collection.name}</span>
            </Link>
          </div>
          <span
            className={cn(
              "flex flex-shrink-0 items-center opacity-0 group-hover:opacity-100 focus-within:opacity-100",
              {
                "opacity-100": isMenuActive,
              }
            )}
          >
            <Menu onOpenChange={setIsMenuActive}>
              <MenuTrigger
                render={
                  <IconButton
                    variant="ghost"
                    size="xs"
                    icon={<Icon icon={AddOutline} />}
                    aria-label={t("wiki_collections.header.add_page")}
                  />
                }
              />
              <MenuContent side="bottom" align="start">
                <MenuItem
                  icon={<Icon icon={AddPageOutline} />}
                  label={t("wiki_collections.menu.create_new_page")}
                  onClick={() => {
                    setIsExpanded(true);
                    void onCreatePage({ collection_id: collectionId });
                  }}
                />
                <MenuItem
                  icon={<Icon icon={LinkPageOutline} />}
                  label={t("wiki_collections.menu.add_existing_page")}
                  onClick={() => setIsAddPagesModalOpen(true)}
                />
              </MenuContent>
            </Menu>
            {canManageCollection && (
              <Menu onOpenChange={setIsMenuActive}>
                <MenuTrigger
                  render={
                    <IconButton
                      variant="ghost"
                      size="xs"
                      icon={<Icon icon={MoreHorizontalOutline} />}
                      aria-label={t("wiki_collections.menu.collection_options")}
                    />
                  }
                />
                <MenuContent side="bottom" align="start">
                  <MenuItem
                    icon={<Icon icon={EditOutline} />}
                    label={t("wiki_collections.menu.edit_collection")}
                    onClick={() => setIsEditModalOpen(true)}
                  />
                  {!collection.is_default && (
                    <MenuItem
                      variant="danger"
                      icon={<Icon icon={DeleteOutline} />}
                      label={t("wiki_collections.delete_modal.title")}
                      onClick={() => setIsDeleteDialogOpen(true)}
                    />
                  )}
                </MenuContent>
              </Menu>
            )}
          </span>
        </SidebarNavItem>
        {isLastChild && <DropIndicator classNames="absolute bottom-0" isVisible={instruction === "reorder-below"} />}
      </div>
      {isExpanded &&
        pageIds.map((pageId, index) => (
          <PageTreeNode
            key={pageId}
            pageId={pageId}
            storeType={storeType}
            variant="sidebar"
            depth={1}
            isLastChild={index === pageIds.length - 1}
            onCreateNestedPage={onCreateNestedPage}
            onDrop={onPageDrop}
          />
        ))}
    </>
  );
});
