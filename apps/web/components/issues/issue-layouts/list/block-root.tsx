/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MutableRefObject } from "react";
import React, { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
// plane helpers
import { useOutsideClickDetector } from "@plane/hooks";
// types
import type { IIssueDisplayProperties, TIssue, TIssueMap } from "@plane/types";
// components
import { cn } from "@plane/utils";
import RenderIfVisible from "@/components/core/render-if-visible-HOC";
import { ListLoaderItemRow } from "@/components/ui/loader/layouts/list-layout-loader";
// hooks
import { useListView } from "@/hooks/store/use-list-view";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";
import { usePlatformOS } from "@/hooks/use-platform-os";
// types
import { HIGHLIGHT_CLASS, getIssueBlockId, isIssueNew } from "../utils";
import { IssueBlock } from "./block";
import { ListDropLine } from "./drop-line";
import type { TRenderQuickActions } from "./list-view-types";
import type { TListRowDropData } from "./utils";
import { getListRowDropPlace, isSubIssueOf } from "./utils";

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
  const [isCurrentBlockDragging, setIsCurrentBlockDragging] = useState(false);
  // ref
  const issueBlockRef = useRef<HTMLDivElement | null>(null);
  // hooks
  const { isMobile } = usePlatformOS();
  const { getRowDropPlace } = useListView();

  useEffect(() => {
    const blockElement = issueBlockRef.current;

    if (!blockElement) return;

    return combine(
      dropTargetForElements({
        element: blockElement,
        canDrop: () => canDropOverIssue,
        getData: ({ input, element, source }): TListRowDropData => ({
          id: issueId,
          type: "ISSUE",
          // a row takes neither itself nor a row it is under
          place: isSubIssueOf(issuesMap, issueId, source.data.id as string)
            ? undefined
            : getListRowDropPlace(element, input.clientY, isExpanded),
        }),
      })
    );
  }, [issueId, issuesMap, isExpanded, issueBlockRef, canDropOverIssue]);

  useOutsideClickDetector(issueBlockRef, () => {
    issueBlockRef?.current?.classList?.remove(HIGHLIGHT_CLASS);
  });

  if (!issueId || !issuesMap[issueId]?.created_at) return null;

  // a nested row is lower when neither it nor its siblings show sub-work items, the rows that get no space above
  const isCompact = nestingLevel > 0 && spacingTop === 0;
  const dropPlace = getRowDropPlace(issueId, groupId);

  return (
    <div
      // the scroll margin keeps a row that is scrolled to clear of the group header
      className={cn("relative scroll-mt-12", {
        "z-[1] bg-accent-primary/10 outline-2 -outline-offset-2 outline-accent-strong": dropPlace === "inside",
      })}
      ref={issueBlockRef}
      id={getIssueBlockId(issueId, groupId)}
      style={{ marginTop: spacingTop }}
    >
      {/* the space above the row takes a drop above the row */}
      <div className="absolute bottom-full w-full" style={{ height: spacingTop }} />
      {dropPlace === "above" && <ListDropLine className="top-0" spacingLeft={spacingLeft} />}
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
      {dropPlace === "below" && <ListDropLine spacingLeft={spacingLeft} />}
    </div>
  );
});
