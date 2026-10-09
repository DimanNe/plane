/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
// types
import type { TPageNavigationTabs } from "@plane/types";
import { cn } from "@plane/utils";
// components
import { ListLayout } from "@/components/core/list";
import { PageTreeNode } from "@/components/pages/nesting/page-tree";
// plane web hooks
import type { EPageStoreType } from "@/hooks/store";
import { usePageStore } from "@/hooks/store";

type TPagesListRoot = {
  pageType: TPageNavigationTabs;
  storeType: EPageStoreType.PROJECT;
};

export const PagesListRoot = observer(function PagesListRoot(props: TPagesListRoot) {
  const { pageType, storeType } = props;
  // states
  const [isDraggedOver, setIsDraggedOver] = useState(false);
  // refs
  const containerRef = useRef<HTMLDivElement>(null);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getPageById, getCurrentProjectFilteredPageIdsByTab, setPageParent } = usePageStore(storeType);
  // derived values
  const filteredPageIds = getCurrentProjectFilteredPageIdsByTab(pageType) ?? [];
  // a page nested under a page of the list shows under it
  const filteredPageIdsSet = new Set(filteredPageIds);
  const rootPageIds = filteredPageIds.filter((pageId) => !filteredPageIdsSet.has(getPageById(pageId)?.parent_id ?? ""));
  const moveErrorTitle = t("page_actions.move_page.toasts.error.title");
  const moveErrorMessage = t("page_actions.move_page.toasts.error.message");

  const handleDrop = useCallback(
    (pageId: string, parentPageId: string | null) => {
      setPageParent(pageId, parentPageId).catch(() =>
        setToast({ type: "error", title: moveErrorTitle, message: moveErrorMessage })
      );
    },
    [moveErrorMessage, moveErrorTitle, setPageParent]
  );

  // a nested page dropped on the list, outside its pages, moves to the top level
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    return dropTargetForElements({
      element,
      canDrop: ({ source }) =>
        source.data.storeType === storeType &&
        typeof source.data.pageId === "string" &&
        !!getPageById(source.data.pageId)?.parent_id,
      onDrag: ({ location }) => setIsDraggedOver(location.current.dropTargets[0]?.element === element),
      onDragLeave: () => setIsDraggedOver(false),
      onDrop: ({ location, source }) => {
        setIsDraggedOver(false);
        if (location.current.dropTargets[0]?.element === element && typeof source.data.pageId === "string")
          handleDrop(source.data.pageId, null);
      },
    });
  }, [getPageById, handleDrop, storeType]);

  return (
    <div ref={containerRef} className={cn("h-full w-full", { "bg-layer-transparent-hover": isDraggedOver })}>
      <ListLayout>
        {rootPageIds.map((pageId) => (
          <PageTreeNode key={pageId} pageId={pageId} storeType={storeType} variant="list" onDrop={handleDrop} />
        ))}
      </ListLayout>
    </div>
  );
});
