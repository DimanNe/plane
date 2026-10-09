/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MutableRefObject } from "react";
import React, { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { attachInstruction, extractInstruction } from "@atlaskit/pragmatic-drag-and-drop-hitbox/tree-item";
import { observer } from "mobx-react";
// plane helpers
import { useOutsideClickDetector } from "@plane/hooks";
// types
import type { IIssueDisplayProperties, InstructionType, TIssue, TIssueMap } from "@plane/types";
// components
import { DropIndicator } from "@plane/blocks/common";
import { cn } from "@plane/utils";
import RenderIfVisible from "@/components/core/render-if-visible-HOC";
import { ListLoaderItemRow } from "@/components/ui/loader/layouts/list-layout-loader";
// hooks
import type { TSelectionHelper } from "@/hooks/use-multiple-select";
import { usePlatformOS } from "@/hooks/use-platform-os";
// types
import { HIGHLIGHT_CLASS, getIssueBlockId, isIssueNew } from "../utils";
import { IssueBlock } from "./block";
import type { TRenderQuickActions } from "./list-view-types";
import { isSubIssueOf } from "./utils";

type Props = {
  issueId: string;
  issuesMap: TIssueMap;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
  quickActions: TRenderQuickActions;
  canEditProperties: (projectId: string | undefined) => boolean;
  displayProperties: IIssueDisplayProperties | undefined;
  nestingLevel: number;
  spacingLeft?: number;
  spacingTop: number;
  hasSubIssues: boolean;
  isExpanded: boolean;
  containerRef: MutableRefObject<HTMLDivElement | null>;
  selectionHelpers: TSelectionHelper;
  groupId: string;
  isDragAllowed: boolean;
  canDropOverIssue: boolean;
  isLastChild?: boolean;
  isEpic?: boolean;
};

export const IssueBlockRoot = observer(function IssueBlockRoot(props: Props) {
  const {
    issueId,
    issuesMap,
    groupId,
    updateIssue,
    quickActions,
    canEditProperties,
    displayProperties,
    nestingLevel,
    spacingLeft = 14,
    spacingTop,
    hasSubIssues,
    isExpanded,
    containerRef,
    isDragAllowed,
    canDropOverIssue,
    isLastChild = false,
    selectionHelpers,
    isEpic = false,
  } = props;
  // states
  const [instruction, setInstruction] = useState<InstructionType | undefined>(undefined);
  const [isCurrentBlockDragging, setIsCurrentBlockDragging] = useState(false);
  // ref
  const issueBlockRef = useRef<HTMLDivElement | null>(null);
  // hooks
  const { isMobile } = usePlatformOS();

  useEffect(() => {
    const blockElement = issueBlockRef.current;

    if (!blockElement) return;

    return combine(
      dropTargetForElements({
        element: blockElement,
        canDrop: () => canDropOverIssue,
        getData: ({ input, element, source }) => {
          const data = { id: issueId, type: "ISSUE" };

          // a drop below a work item that shows its sub-work items makes the first of them
          return attachInstruction(data, {
            input,
            element,
            currentLevel: 0,
            indentPerLevel: 0,
            mode: isExpanded ? "expanded" : "standard",
            block: isSubIssueOf(issuesMap, issueId, source.data.id as string)
              ? ["reorder-above", "reorder-below", "make-child"]
              : [],
          });
        },
        onDrag: ({ self }) => {
          setInstruction(extractInstruction(self?.data)?.type);
        },
        onDragLeave: () => {
          setInstruction(undefined);
        },
        onDrop: () => {
          setInstruction(undefined);
        },
      })
    );
  }, [issueId, issuesMap, isExpanded, issueBlockRef, canDropOverIssue, setInstruction]);

  useOutsideClickDetector(issueBlockRef, () => {
    issueBlockRef?.current?.classList?.remove(HIGHLIGHT_CLASS);
  });

  if (!issueId || !issuesMap[issueId]?.created_at) return null;

  // a nested row is lower when neither it nor its siblings show sub-work items, the rows that get no space above
  const isCompact = nestingLevel > 0 && spacingTop === 0;

  return (
    <div
      // the scroll margin keeps a row that is scrolled to clear of the group header and the quick add row
      className={cn("relative scroll-my-12", {
        "z-[1] bg-accent-primary/10 outline-2 -outline-offset-2 outline-accent-strong": instruction === "make-child",
      })}
      ref={issueBlockRef}
      id={getIssueBlockId(issueId, groupId)}
      style={{ marginTop: spacingTop }}
    >
      {/* the space above the row takes a drop above the row */}
      <div className="absolute bottom-full w-full" style={{ height: spacingTop }} />
      <div className="absolute top-0 right-0 z-[2] pl-page-x" style={{ left: spacingLeft }}>
        <DropIndicator isVisible={instruction === "reorder-above"} />
      </div>
      <RenderIfVisible
        key={`${issueId}`}
        root={containerRef}
        classNames={`relative ${isLastChild && !isExpanded ? "" : "border-b border-b-subtle"}`}
        verticalOffset={100}
        defaultValue={issuesMap[issueId] ? isIssueNew(issuesMap[issueId]) : false}
        placeholderChildren={<ListLoaderItemRow shouldAnimate={false} renderForPlaceHolder defaultPropertyCount={4} />}
        shouldRecordHeights={isMobile}
      >
        <IssueBlock
          issueId={issueId}
          issuesMap={issuesMap}
          groupId={groupId}
          updateIssue={updateIssue}
          quickActions={quickActions}
          canEditProperties={canEditProperties}
          displayProperties={displayProperties}
          hasSubIssues={hasSubIssues}
          isExpanded={isExpanded}
          nestingLevel={nestingLevel}
          spacingLeft={spacingLeft}
          selectionHelpers={selectionHelpers}
          canDrag={isDragAllowed}
          isCompact={isCompact}
          isCurrentBlockDragging={isCurrentBlockDragging}
          setIsCurrentBlockDragging={setIsCurrentBlockDragging}
          isEpic={isEpic}
        />
      </RenderIfVisible>
      <div className="absolute right-0 z-[2] pl-page-x" style={{ left: spacingLeft }}>
        <DropIndicator isVisible={instruction === "reorder-below"} />
      </div>
    </div>
  );
});
