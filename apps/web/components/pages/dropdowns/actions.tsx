/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { isValidElement, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import {
  ArchiveOutline,
  CopyOutline,
  DeleteOutline,
  ExportOutline,
  GlobeOutline,
  LinkOutline,
  LockOutline,
  LockedOutline,
  MoreHorizontalOutline,
  NewTabOutline,
  RemoveOutline,
  RestoreOutline,
  UnlockedOutline,
} from "@makeplane/propel/icons";
// constants
import { EPageAccess } from "@plane/constants";
// plane ui
import { useTranslation } from "@plane/i18n";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import type { TContextMenuItem } from "@plane/blocks/context-menu";
import { ContextMenu, getRenderableItems, resolveItemVariant } from "@plane/blocks/context-menu";
import { setToast } from "@plane/blocks/toast";
// components
import { DeletePageModal } from "@/components/pages/modals/delete-page-modal";
// hooks
import { usePageOperations } from "@/hooks/use-page-operations";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { usePageFlag } from "@/hooks/use-page-flag";
// store types
import type { TPageInstance } from "@/store/pages/base-page";

export type TPageActions =
  | "full-screen"
  | "sticky-toolbar"
  | "copy-markdown"
  | "toggle-lock"
  | "toggle-access"
  | "open-in-new-tab"
  | "copy-link"
  | "make-a-copy"
  | "archive-restore"
  | "delete"
  | "version-history"
  | "export"
  | "move"
  | "toggle-lock-with-nested-pages"
  | "remove-from-collection";

type Props = {
  extraOptions?: (TContextMenuItem & { key: TPageActions })[];
  optionsOrder: TPageActions[];
  page: TPageInstance;
  parentRef?: React.RefObject<HTMLElement | null>;
  storeType: EPageStoreType;
};

export const PageActions = observer(function PageActions(props: Props) {
  const { extraOptions, optionsOrder, page, parentRef, storeType } = props;
  // plane hooks
  const { t } = useTranslation();
  // states
  const [deletePageModal, setDeletePageModal] = useState(false);
  const [movePageModal, setMovePageModal] = useState(false);
  // params
  const { workspaceSlug } = useParams();
  // page flag
  const { isMovePageEnabled } = usePageFlag({
    workspaceSlug: workspaceSlug?.toString() ?? "",
  });
  // page operations
  const { pageOperations } = usePageOperations({
    page,
  });
  // store hooks
  const { getNestedPageIds } = usePageStore(storeType);
  const { getCollectionById, movePage } = usePageStore(EPageStoreType.WORKSPACE);
  // derived values
  const hasNestedPages = !!page.id && getNestedPageIds(page.id).length > 0;
  const collection = page.collection_id ? getCollectionById(page.collection_id) : undefined;
  const {
    access,
    archived_at,
    is_locked,
    canCurrentUserArchivePage,
    canCurrentUserChangeAccess,
    canCurrentUserDeletePage,
    canCurrentUserDuplicatePage,
    canCurrentUserLockPage,
    canCurrentUserMovePage,
  } = page;
  // menu items
  const MENU_ITEMS = useMemo(
    function MENU_ITEMS() {
      const menuItems: (TContextMenuItem & { key: TPageActions })[] = [
        {
          key: "toggle-lock",
          action: () => {
            pageOperations.toggleLock();
          },
          title: is_locked ? "Unlock" : "Lock",
          icon: is_locked ? UnlockedOutline : LockedOutline,
          shouldRender: canCurrentUserLockPage,
        },
        {
          key: "toggle-lock-with-nested-pages",
          action: () => {
            pageOperations.toggleLock(true);
          },
          title: t(is_locked ? "nested_pages.unlock" : "nested_pages.lock"),
          icon: is_locked ? UnlockedOutline : LockedOutline,
          shouldRender: canCurrentUserLockPage && hasNestedPages,
        },
        {
          key: "toggle-access",
          action: () => {
            pageOperations.toggleAccess();
          },
          title: access === EPageAccess.PUBLIC ? "Make private" : "Make public",
          icon: access === EPageAccess.PUBLIC ? LockOutline : GlobeOutline,
          shouldRender: canCurrentUserChangeAccess && !archived_at,
        },
        {
          key: "open-in-new-tab",
          action: pageOperations.openInNewTab,
          title: "Open in new tab",
          icon: NewTabOutline,
          shouldRender: true,
        },
        {
          key: "copy-link",
          action: pageOperations.copyLink,
          title: "Copy link",
          icon: LinkOutline,
          shouldRender: true,
        },
        {
          key: "make-a-copy",
          action: () => {
            pageOperations.duplicate();
          },
          title: "Make a copy",
          icon: CopyOutline,
          shouldRender: canCurrentUserDuplicatePage,
        },
        {
          key: "archive-restore",
          action: () => {
            pageOperations.toggleArchive();
          },
          title: archived_at ? "Restore" : "Archive",
          icon: archived_at ? RestoreOutline : ArchiveOutline,
          shouldRender: canCurrentUserArchivePage,
        },
        {
          key: "delete",
          action: () => {
            setDeletePageModal(true);
          },
          title: "Delete",
          icon: DeleteOutline,
          shouldRender: canCurrentUserDeletePage && !!archived_at,
        },
        {
          key: "move",
          action: () => setMovePageModal(true),
          title: "Move",
          icon: ExportOutline,
          shouldRender: canCurrentUserMovePage && isMovePageEnabled,
        },
        {
          key: "remove-from-collection",
          action: () => {
            if (!page.id) return;
            movePage(page.id, { collection_id: null })
              .then(() =>
                setToast({
                  type: "success",
                  title: t("toast.success"),
                  message: t("page_actions.remove_from_collection.success_message"),
                })
              )
              .catch(() =>
                setToast({
                  type: "error",
                  title: t("toast.error"),
                  message: t("page_actions.remove_from_collection.error_message"),
                })
              );
          },
          title: t("page_actions.remove_from_collection.label"),
          icon: RemoveOutline,
          // a nested page follows its parent, and a public page always is in a collection
          shouldRender: canCurrentUserMovePage && !page.parent_id && !!collection && !collection.is_default,
        },
      ];
      if (extraOptions) {
        menuItems.push(...extraOptions);
      }
      return menuItems;
    },
    [
      extraOptions,
      is_locked,
      canCurrentUserLockPage,
      access,
      canCurrentUserChangeAccess,
      archived_at,
      canCurrentUserDuplicatePage,
      canCurrentUserArchivePage,
      canCurrentUserDeletePage,
      canCurrentUserMovePage,
      isMovePageEnabled,
      pageOperations,
      page,
      hasNestedPages,
      collection,
      movePage,
      t,
    ]
  );
  // arrange options
  const arrangedOptions = useMemo<(TContextMenuItem & { key: TPageActions })[]>(
    () =>
      optionsOrder
        .map((key) => MENU_ITEMS.find((item) => item.key === key))
        .filter((item): item is TContextMenuItem & { key: TPageActions } => !!item),
    [optionsOrder, MENU_ITEMS]
  );

  return (
    <>
      <DeletePageModal
        isOpen={deletePageModal}
        onClose={() => setDeletePageModal(false)}
        page={page}
        storeType={storeType}
      />
      {parentRef && <ContextMenu parentRef={parentRef} items={arrangedOptions} />}
      <Menu>
        <MenuTrigger
          render={
            <IconButton
              variant="ghost"
              size="sm"
              aria-label={t("aria_labels.common.more_actions")}
              icon={<Icon icon={MoreHorizontalOutline} />}
              // the list row is a link: keep the trigger from navigating or bubbling to it
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") e.stopPropagation();
              }}
            />
          }
        />
        <MenuContent side="bottom" align="end">
          {getRenderableItems(arrangedOptions).map((item) => (
            <MenuItem
              key={item.key}
              variant={resolveItemVariant(item)}
              label={item.title ?? ""}
              description={item.description}
              icon={item.icon && <Icon icon={item.icon} />}
              // `customContent` (the full-width / sticky-toolbar switches) sits at the row's inline end.
              trailing={isValidElement(item.customContent) ? item.customContent : undefined}
              disabled={item.disabled}
              closeOnClick={item.closeOnClick}
              onClick={(e) => {
                e.stopPropagation();
                item.action?.();
              }}
            />
          ))}
        </MenuContent>
      </Menu>
    </>
  );
});
