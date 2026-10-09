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
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { AddOutline, ChevronRightOutline, PagesOutline } from "@makeplane/propel/icons";
import { DropIndicator } from "@plane/blocks/common";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import { useTranslation } from "@plane/i18n";
import type { InstructionType } from "@plane/types";
import { cn, getPageName } from "@plane/utils";
// components
import { PageListBlock } from "@/components/pages/list/block";
import { SidebarNavItem } from "@/components/sidebar/sidebar-navigation";
// hooks
import type { EPageStoreType } from "@/hooks/store";
import { usePageStore } from "@/hooks/store";

type TPageTreeNodeProps = {
  pageId: string;
  storeType: EPageStoreType;
  variant: "sidebar" | "list";
  depth?: number;
  isLastChild?: boolean;
  onCreateNestedPage?: (parentPageId: string) => void;
  // makes the tree a drag and drop tree: a page is dropped on a page to nest it, or above or below it to place it
  onDrop?: (pageId: string, targetPageId: string, instruction: InstructionType) => void;
};

export const PageTreeNode = observer(function PageTreeNode(props: TPageTreeNodeProps) {
  const { pageId, storeType, variant, depth = 0, isLastChild = false, onCreateNestedPage, onDrop } = props;
  // states
  const [isExpanded, setIsExpanded] = useState(false);
  const [instruction, setInstruction] = useState<InstructionType | undefined>(undefined);
  // refs
  const rowRef = useRef<HTMLDivElement>(null);
  // params
  const { pageId: activePageId } = useParams();
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getPageById, getChildPageIds, getNestedPageIds } = usePageStore(storeType);
  // derived values
  const page = getPageById(pageId);
  const childPageIds = getChildPageIds(pageId);
  const canReorder = variant === "sidebar";
  const canMovePage = !!page?.canCurrentUserMovePage;
  const isActivePageNestedUnder = !!activePageId && getNestedPageIds(pageId).includes(activePageId);

  // the path to the open page stays visible
  useEffect(() => {
    if (isActivePageNestedUnder) setIsExpanded(true);
  }, [isActivePageNestedUnder]);

  useEffect(() => {
    const element = rowRef.current;
    if (!element || !onDrop) return;

    return combine(
      draggable({
        element,
        canDrag: () => canMovePage,
        getInitialData: () => ({ pageId, storeType }),
      }),
      dropTargetForElements({
        element,
        canDrop: ({ source }) =>
          source.data.storeType === storeType &&
          typeof source.data.pageId === "string" &&
          source.data.pageId !== pageId &&
          !getNestedPageIds(source.data.pageId).includes(pageId),
        getData: ({ input, element: targetElement }) => {
          const blockedInstructions: InstructionType[] = [];
          if (!canReorder) blockedInstructions.push("reorder-above");
          if (!canReorder || !isLastChild) blockedInstructions.push("reorder-below");

          return attachInstruction(
            { pageId },
            {
              input,
              element: targetElement,
              currentLevel: depth,
              indentPerLevel: 0,
              mode: "standard",
              block: blockedInstructions,
            }
          );
        },
        onDrag: ({ self }) => {
          const dropInstruction = extractInstruction(self.data)?.type;
          setInstruction(dropInstruction === "instruction-blocked" ? "make-child" : dropInstruction);
        },
        onDragLeave: () => {
          setInstruction(undefined);
        },
        onDrop: ({ self, source }) => {
          setInstruction(undefined);
          const dropInstruction = extractInstruction(self.data)?.type;
          if (!dropInstruction || typeof source.data.pageId !== "string") return;
          if (dropInstruction === "reorder-above" || dropInstruction === "reorder-below") {
            onDrop(source.data.pageId, pageId, dropInstruction);
          } else {
            onDrop(source.data.pageId, pageId, "make-child");
            setIsExpanded(true);
          }
        },
      })
    );
  }, [canMovePage, canReorder, depth, getNestedPageIds, isLastChild, onDrop, pageId, storeType]);

  if (!page) return null;

  const expandToggle =
    childPageIds.length > 0 ? (
      <button
        type="button"
        className="grid size-4 flex-shrink-0 place-items-center rounded-sm text-placeholder hover:text-secondary"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsExpanded(!isExpanded);
        }}
        aria-expanded={isExpanded}
        aria-label={t(isExpanded ? "wiki_collections.list.collapse_page" : "wiki_collections.list.expand_page")}
      >
        <ChevronRightOutline className={cn("size-3.5 transition-transform", { "rotate-90": isExpanded })} />
      </button>
    ) : (
      <span className="size-4 flex-shrink-0" />
    );
  const indentation = <span className="flex-shrink-0" style={{ width: depth * 16 }} />;

  return (
    <>
      <div
        ref={rowRef}
        className={cn("relative", { "rounded-md bg-layer-transparent-hover": instruction === "make-child" })}
      >
        {canReorder && <DropIndicator classNames="absolute top-0" isVisible={instruction === "reorder-above"} />}
        {variant === "list" ? (
          <PageListBlock
            pageId={pageId}
            storeType={storeType}
            prependTitleElement={
              <span className="mr-1.5 flex items-center">
                {indentation}
                {expandToggle}
              </span>
            }
          />
        ) : (
          <SidebarNavItem isActive={activePageId === pageId} className="gap-1">
            <div className="flex min-w-0 flex-grow items-center gap-1">
              {indentation}
              {expandToggle}
              <Link
                href={page.getRedirectionLink()}
                className="flex min-w-0 flex-grow items-center gap-1.5"
                draggable={false}
              >
                <span className="grid size-4 flex-shrink-0 place-items-center">
                  {page.logo_props?.in_use ? (
                    <Logo logo={page.logo_props} size={14} type="lucide" />
                  ) : (
                    <PagesOutline className="size-3.5 text-tertiary" />
                  )}
                </span>
                <span className="truncate text-13 leading-5 font-medium">{getPageName(page.name)}</span>
              </Link>
            </div>
            {onCreateNestedPage && page.canCurrentUserEditPage && (
              <span className="flex-shrink-0 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
                <IconButton
                  variant="ghost"
                  size="xs"
                  icon={<Icon icon={AddOutline} />}
                  aria-label={t("nested_pages.add")}
                  onClick={() => {
                    setIsExpanded(true);
                    onCreateNestedPage(pageId);
                  }}
                />
              </span>
            )}
          </SidebarNavItem>
        )}
        {canReorder && isLastChild && (
          <DropIndicator classNames="absolute bottom-0" isVisible={instruction === "reorder-below"} />
        )}
      </div>
      {isExpanded &&
        childPageIds.map((childPageId, index) => (
          <PageTreeNode
            {...props}
            key={childPageId}
            pageId={childPageId}
            depth={depth + 1}
            isLastChild={index === childPageIds.length - 1}
          />
        ))}
    </>
  );
});
