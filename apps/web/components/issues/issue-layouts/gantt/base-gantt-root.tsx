/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useCallback, useEffect, useState } from "react";
import { when } from "mobx";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { ALL_ISSUES, EIssueFilterType, EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import type { EIssuesStoreType } from "@plane/types";
import { EIssueLayoutTypes } from "@plane/types";
import { renderFormattedPayloadDate } from "@plane/utils";
// components
import { LayoutErrorBoundary } from "@/components/common/layout-error-boundary";
import { WorkItemsTimeline } from "@/components/timeline/root";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
import { useUserPermissions } from "@/hooks/store/user";
import { useIssueStoreType } from "@/hooks/use-issue-layout-store";
import { useIssuesActions } from "@/hooks/use-issues-actions";
// local imports
import { IssueLayoutHOC } from "../issue-layout-HOC";
import { GanttQuickAddIssueButton, QuickAddIssueRoot } from "../quick-add";

interface IBaseGanttRoot {
  viewId?: string | undefined;
  isCompletedCycle?: boolean;
  isEpic?: boolean;
}

export type GanttStoreType =
  | EIssuesStoreType.PROJECT
  | EIssuesStoreType.MODULE
  | EIssuesStoreType.CYCLE
  | EIssuesStoreType.PROJECT_VIEW
  | EIssuesStoreType.EPIC;

export const BaseGanttRoot = observer(function BaseGanttRoot(props: IBaseGanttRoot) {
  const { viewId, isCompletedCycle = false, isEpic = false } = props;
  // router
  const { projectId } = useParams();
  // states
  // the list goes into the manual order under a line that was moved
  const [isOrderedManually, setIsOrderedManually] = useState(false);

  const storeType = useIssueStoreType() as GanttStoreType;
  const { issues, issuesFilter } = useIssues(storeType);
  const { fetchIssues, fetchNextIssues, updateIssue, quickAddIssue, updateFilters } = useIssuesActions(storeType);
  // store hooks
  const { allowPermissions } = useUserPermissions();

  const appliedDisplayFilters = issuesFilter.issueFilters?.displayFilters;
  // derived values
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + 1);

  useEffect(() => {
    fetchIssues("init-loader", { canGroup: false, perPageCount: 100 }, viewId);
  }, [fetchIssues, storeType, viewId]);

  const issuesIds = (issues.groupedIssueIds?.[ALL_ISSUES] as string[]) ?? [];
  const nextPageResults = issues.getPaginationData(undefined, undefined)?.nextPageResults;

  const { enableIssueCreation } = issues?.viewFlags || {};

  const loadMoreIssues = useCallback(() => {
    fetchNextIssues();
  }, [fetchNextIssues]);

  // Every line of the list, also of the pages that are not loaded yet, page after page: each tells where the next
  // begins. A fetch of the list that is going on ends first: it gives the pages their order.
  const loadAllIssues = async (): Promise<void> => {
    await when(() => !issues.getIssueLoader());
    if (issues.getPaginationData(undefined, undefined)?.nextPageResults && (await fetchNextIssues()))
      return loadAllIssues();
  };

  // the list is fetched again in its new order: the timeline stays meanwhile
  const orderManually = async () => {
    setIsOrderedManually(true);
    try {
      await updateFilters(projectId.toString(), EIssueFilterType.DISPLAY_FILTERS, { order_by: "sort_order" });
      await when(() => !issues.getIssueLoader());
    } finally {
      setIsOrderedManually(false);
    }
  };

  const isAllowed = allowPermissions([EUserPermissions.ADMIN, EUserPermissions.MEMBER], EUserPermissionsLevel.PROJECT);
  const quickAdd =
    enableIssueCreation && isAllowed && !isCompletedCycle ? (
      <QuickAddIssueRoot
        layout={EIssueLayoutTypes.GANTT}
        QuickAddButton={GanttQuickAddIssueButton}
        containerClassName="sticky bottom-0 z-[1]"
        prePopulatedData={{
          start_date: renderFormattedPayloadDate(new Date()),
          target_date: renderFormattedPayloadDate(targetDate),
        }}
        quickAddCallback={quickAddIssue}
        isEpic={isEpic}
      />
    ) : undefined;

  // The loader and the empty state of the layout stand in the place of the timeline, so a list that is fetched
  // again draws the timeline anew. Not while the list goes into the manual order under a line that was moved:
  // the timeline stays then, with its view and its lines where they are.
  if (!issues.getGroupIssueCount(undefined, undefined, false) && !isOrderedManually)
    return <IssueLayoutHOC layout={EIssueLayoutTypes.GANTT}>{null}</IssueLayoutHOC>;

  return (
    <LayoutErrorBoundary>
      <div className="h-full w-full">
        <WorkItemsTimeline
          workItemIds={issuesIds}
          isEditable={isAllowed}
          showOnlyLeaves={!!appliedDisplayFilters?.show_only_leaves}
          onShowOnlyLeavesChange={(show_only_leaves) =>
            updateFilters(projectId.toString(), EIssueFilterType.DISPLAY_FILTERS, { show_only_leaves })
          }
          updateSortOrder={(issue, sort_order) => updateIssue?.(issue.project_id, issue.id, { sort_order })}
          orderManually={appliedDisplayFilters?.order_by === "sort_order" ? undefined : orderManually}
          loadAll={loadAllIssues}
          quickAdd={quickAdd}
          loadMore={nextPageResults && !issues.getIssueLoader() ? loadMoreIssues : undefined}
        />
      </div>
    </LayoutErrorBoundary>
  );
});
