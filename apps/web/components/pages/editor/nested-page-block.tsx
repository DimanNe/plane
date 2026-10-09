/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import Link from "next/link";
// plane imports
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { ArchiveOutline, DeleteOutline, MoreHorizontalOutline, PagesOutline } from "@makeplane/propel/icons";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import { cn, getPageName } from "@plane/utils";
// components
import { useMovePage } from "@/components/pages/wiki/move-page-provider";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

type Props = {
  pageId: string;
  storeType: EPageStoreType;
  isEditable: boolean;
  isDeleteRequested: boolean;
  toggleDeleteRequest: (value: boolean) => void;
  deleteBlock: () => void;
};

export const NestedPageBlock = observer(function NestedPageBlock(props: Props) {
  const { pageId, storeType, isEditable, isDeleteRequested, toggleDeleteRequest, deleteBlock } = props;
  // states
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDraggedOver, setIsDraggedOver] = useState(false);
  // refs
  const blockRef = useRef<HTMLDivElement>(null);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getPageById, removePage } = usePageStore(storeType);
  const { getNestedPageIds } = usePageStore(EPageStoreType.WORKSPACE);
  const movePage = useMovePage();
  // derived values
  const page = getPageById(pageId);
  const isWikiPage = storeType === EPageStoreType.WORKSPACE;
  const isPageAvailable = !!page;
  const canDeletePage = !!page?.canCurrentUserDeletePage;

  // deleting the block asks to delete the page; without a page the user can delete, only the block goes
  useEffect(() => {
    if (isDeleteRequested && !canDeletePage) deleteBlock();
  }, [canDeletePage, deleteBlock, isDeleteRequested]);

  // a page of the wiki sidebar is dropped on the block to nest it under the page of the block
  useEffect(() => {
    const element = blockRef.current;
    if (!element || !isEditable || !isWikiPage || !isPageAvailable) return;

    return dropTargetForElements({
      element,
      canDrop: ({ source }) =>
        source.data.storeType === storeType &&
        typeof source.data.pageId === "string" &&
        source.data.pageId !== pageId &&
        !getNestedPageIds(source.data.pageId).includes(pageId),
      onDragEnter: () => setIsDraggedOver(true),
      onDragLeave: () => setIsDraggedOver(false),
      onDrop: ({ source }) => {
        setIsDraggedOver(false);
        if (typeof source.data.pageId === "string") movePage(source.data.pageId, { parent_id: pageId });
      },
    });
  }, [getNestedPageIds, isEditable, isPageAvailable, isWikiPage, movePage, pageId, storeType]);

  const handleArchive = async () => {
    if (!page) return false;
    await page.archive({});
    // `archive` reports a failure only by leaving the page unarchived
    if (!page.archived_at)
      setToast({
        type: "error",
        title: t("toast.error"),
        message: t("nested_pages.block.archive_error"),
      });
    return !!page.archived_at;
  };

  const handleDelete = async () => {
    if (!page) return;
    setIsDeleting(true);
    // only an archived page can be deleted; a deleted page leaves the store, and its block goes with it
    if (page.archived_at || (await handleArchive()))
      await removePage({ pageId }).catch(() =>
        setToast({
          type: "error",
          title: t("toast.error"),
          message: t("nested_pages.block.delete_error"),
        })
      );
    setIsDeleting(false);
  };

  if (!page)
    return (
      <div className="not-prose my-2 flex items-center gap-2 rounded-md border border-subtle px-3 py-2 text-13 text-placeholder">
        <PagesOutline className="size-4 flex-shrink-0" />
        {t("nested_pages.block.not_available")}
      </div>
    );

  return (
    <>
      <ConfirmDialog
        isOpen={isDeleteRequested && canDeletePage}
        handleClose={() => toggleDeleteRequest(false)}
        handleSubmit={handleDelete}
        isSubmitting={isDeleting}
        title={t("nested_pages.block.delete_title")}
        content={t(
          isWikiPage ? "nested_pages.block.delete_wiki_description" : "nested_pages.block.delete_project_description",
          { name: getPageName(page.name) }
        )}
      />
      <div
        ref={blockRef}
        className={cn(
          "not-prose my-2 flex items-center gap-2 rounded-md border border-subtle bg-layer-1 px-3 py-2 hover:bg-layer-1-hover",
          { "border-accent-strong": isDraggedOver }
        )}
      >
        <Link href={page.getRedirectionLink()} className="block min-w-0 flex-grow" draggable={false}>
          {/* the editor opens the links it finds between a click and the closest div in a new tab */}
          <div className="flex items-center gap-2 text-13 font-medium text-primary">
            <span className="grid size-4 flex-shrink-0 place-items-center">
              {page.logo_props?.in_use ? (
                <Logo logo={page.logo_props} size={16} type="lucide" />
              ) : (
                <PagesOutline className="size-4 text-tertiary" />
              )}
            </span>
            <span className="truncate">{getPageName(page.name)}</span>
            {page.archived_at && <ArchiveOutline className="size-3.5 flex-shrink-0 text-tertiary" />}
          </div>
        </Link>
        {isEditable && (page.canCurrentUserArchivePage || canDeletePage) && (
          <Menu>
            <MenuTrigger
              render={
                <IconButton
                  variant="ghost"
                  size="xs"
                  icon={<Icon icon={MoreHorizontalOutline} />}
                  aria-label={t("aria_labels.common.more_actions")}
                />
              }
            />
            <MenuContent side="bottom" align="end">
              {page.canCurrentUserArchivePage && !page.archived_at && (
                <MenuItem
                  icon={<Icon icon={ArchiveOutline} />}
                  label={t("archive")}
                  onClick={() => void handleArchive()}
                />
              )}
              {canDeletePage && (
                <MenuItem
                  variant="danger"
                  icon={<Icon icon={DeleteOutline} />}
                  label={t("delete")}
                  onClick={() => toggleDeleteRequest(true)}
                />
              )}
            </MenuContent>
          </Menu>
        )}
      </div>
    </>
  );
});
