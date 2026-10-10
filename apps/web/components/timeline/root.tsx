/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useEffect, useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane imports
import { PROJECT_TIMELINE_DEPENDENCIES } from "@plane/constants";
import type { TIssue } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useUserPermissions } from "@/hooks/store/user";
import { useIssuesTimeLineStore } from "@/hooks/use-timeline-chart";
// local imports
import { getParents } from "./bar";
import { TimelineChart } from "./chart";
import type { TTimelineOperation } from "./operation";

type Props = {
  workItemIds: string[];
  // a day the timeline shows when it opens, besides its bars and today
  focusDate?: string | null;
  isEditable: boolean;
  showOnlyLeaves: boolean;
  onShowOnlyLeavesChange: (showOnlyLeaves: boolean) => void;
  // saves the place of a work item in the manual order; given when the work items are in that order
  updateSortOrder?: (workItem: TIssue, sortOrder: number) => void;
  quickAdd?: ReactNode;
  loadMore?: () => void;
};

// the distance in the manual order of a line moved to the first or the last place from the line that was there
const SORT_ORDER_STEP = 1000;

/**
 * The timeline of work items. What it draws is the plan the schedule store computes: of what is stored, or of
 * the operation that is going on.
 */
export const WorkItemsTimeline = observer(function WorkItemsTimeline(props: Props) {
  const { workItemIds, showOnlyLeaves, updateSortOrder, ...chartProps } = props;
  // router
  const { workspaceSlug: routerWorkspaceSlug, projectId: routerProjectId } = useParams();
  const workspaceSlug = routerWorkspaceSlug.toString();
  const projectId = routerProjectId.toString();
  // store hooks
  const {
    issue: { getIssueById },
    rootIssueStore,
  } = useIssueDetail();
  const { schedule, fetchDependencies } = useIssuesTimeLineStore();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  // derived values
  const currentProjectRole = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId);
  // a leaf is a work item without sub-work items; work items are independent here, whatever is shown of their parents
  const taskIds = showOnlyLeaves
    ? workItemIds.filter((workItemId) => !getIssueById(workItemId)?.sub_issues_count)
    : workItemIds;

  // A bar names the parents of its work item. The list may not have loaded one: a filter leaves it out, or it is
  // on a later page.
  const missingParentIds = workItemIds
    .flatMap((workItemId) => {
      const workItem = getIssueById(workItemId);
      const topParentId = workItem && (getParents(workItem, getIssueById)[0] ?? workItem).parent_id;
      return topParentId && !getIssueById(topParentId) ? [topParentId] : [];
    })
    .join();
  useEffect(() => {
    if (missingParentIds) rootIssueStore.issues.getIssues(workspaceSlug, projectId, missingParentIds.split(","));
  }, [missingParentIds, rootIssueStore, workspaceSlug, projectId]);

  // Fetched every time the timeline opens: the store computes the plan from the answer, and saves the computed
  // dates where the stored ones differ.
  useSWR(
    PROJECT_TIMELINE_DEPENDENCIES(projectId, currentProjectRole),
    () => fetchDependencies(workspaceSlug, projectId),
    { revalidateOnFocus: false }
  );

  const operation: TTimelineOperation = useMemo(
    () => ({
      begin: () => schedule.beginOperation(workspaceSlug, projectId),
      preview: (plan) => {
        schedule.previewOperation(plan);
      },
      commit: () => {
        void schedule.commitOperation();
      },
      abort: () => {
        // an operation that is being saved ends by itself
        if (!schedule.operation?.isSaving) schedule.abortOperation();
      },
    }),
    [schedule, workspaceSlug, projectId]
  );

  // an operation holds back every change of the plan made elsewhere until it ends, so none outlives the timeline
  useEffect(() => operation.abort, [operation]);

  // The moved line takes a place in the manual order between its new neighbours. Work items often share a place
  // (the server numbers them per state), so the lines that follow the moved one without being after the line
  // before it get places too, in the order they are in.
  const handleLineMove = (taskId: string, lineIndex: number) => {
    const sourceIndex = taskIds.indexOf(taskId);
    if (!updateSortOrder || lineIndex === sourceIndex || lineIndex === sourceIndex + 1) return;
    const getSortOrder = (workItemId: string | undefined) =>
      workItemId ? getIssueById(workItemId)?.sort_order : undefined;
    const following = taskIds.slice(lineIndex).filter((workItemId) => workItemId !== taskId);
    const before = getSortOrder(taskIds[lineIndex - 1]) ?? (getSortOrder(following[0]) ?? 0) - 2 * SORT_ORDER_STEP;
    const sharedCount = following.findIndex((workItemId) => (getSortOrder(workItemId) ?? 0) > before);
    const moved = [taskId, ...following.slice(0, sharedCount === -1 ? undefined : sharedCount)];
    const after = getSortOrder(following[moved.length - 1]) ?? before + (moved.length + 1) * SORT_ORDER_STEP;
    moved.forEach((workItemId, index) => {
      const workItem = getIssueById(workItemId);
      if (workItem) updateSortOrder(workItem, before + ((after - before) * (index + 1)) / (moved.length + 1));
    });
  };

  return (
    <TimelineChart
      taskIds={taskIds}
      plan={schedule.getPlan(projectId)}
      schedule={schedule.getSchedule(projectId)}
      operation={operation}
      showOnlyLeaves={showOnlyLeaves}
      onLineMove={updateSortOrder && handleLineMove}
      {...chartProps}
    />
  );
});
