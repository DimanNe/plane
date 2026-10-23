/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MutableRefObject } from "react";
import { observer } from "mobx-react";
// components
import type { TIssue, IIssueDisplayProperties, TIssueMap, TGroupedIssues } from "@plane/types";
// hooks
import { useListView } from "@/hooks/store/use-list-view";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";
// types
import { IssueBlockRoot } from "./block-root";
import type { TRenderQuickActions } from "./list-view-types";
import { LIST_ROW_INDENT, LIST_ROW_SPACING, getListRows } from "./utils";

interface Props {
  issueIds: TGroupedIssues | any;
  issueIdsOfList: Set<string>;
  issuesMap: TIssueMap;
  groupId: string;
  canEditProperties: (projectId: string | undefined) => boolean;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
  quickActions: TRenderQuickActions;
  displayProperties: IIssueDisplayProperties | undefined;
  containerRef: MutableRefObject<HTMLDivElement | null>;
  isDragAllowed: boolean;
  canDropOverIssue: boolean;
  selectionHelpers: TSelectionHelper;
  isEpic?: boolean;
}

export const IssueBlocksList = observer(function IssueBlocksList(props: Props) {
  const {
    issueIds,
    issueIdsOfList,
    issuesMap,
    groupId,
    updateIssue,
    quickActions,
    displayProperties,
    canEditProperties,
    containerRef,
    selectionHelpers,
    isDragAllowed,
    canDropOverIssue,
    isEpic = false,
  } = props;
  // store hooks
  const { collapsedIssueIds } = useListView();

  return (
    <div className="relative h-full w-full">
      {issueIds &&
        getListRows(issueIds, issuesMap, collapsedIssueIds, issueIdsOfList).map((row, index, rows) => (
          <IssueBlockRoot
            key={row.issueId}
            issueId={row.issueId}
            issuesMap={issuesMap}
            updateIssue={updateIssue}
            quickActions={quickActions}
            canEditProperties={canEditProperties}
            displayProperties={displayProperties}
            nestingLevel={row.nestingLevel}
            spacingLeft={row.nestingLevel * LIST_ROW_INDENT}
            spacingTop={row.spacingLevel * LIST_ROW_SPACING}
            hasSubIssues={row.hasSubIssues}
            isExpanded={row.isExpanded}
            isInAnotherGroup={row.isInAnotherGroup}
            containerRef={containerRef}
            selectionHelpers={selectionHelpers}
            groupId={groupId}
            isLastChild={index === rows.length - 1}
            isDragAllowed={isDragAllowed}
            canDropOverIssue={canDropOverIssue}
            isEpic={isEpic}
          />
        ))}
    </div>
  );
});
