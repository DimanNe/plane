/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { isEqual } from "lodash-es";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane imports
import { PROJECT_TIMELINE_DEPENDENCIES } from "@plane/constants";
import { useLatestCallback } from "@plane/hooks";
import type { IBlockUpdateDependencyData, TIssue, TTimelineDependency, TTimelineDependencyTypes } from "@plane/types";
// components
import { TimelineRelationModal } from "@/components/gantt-chart/dependency/relation-modal";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useUserPermissions } from "@/hooks/store/user";
import { useIssuesTimeLineStore } from "@/hooks/use-timeline-chart";
// local imports
import { getParents } from "./bar";
import { TimelineChart } from "./chart";
import { getDateOfDay, getDayOfDate } from "./scale";
import type { TArrowKind, TSchedule, TScheduleArrow, TTimelineChange, TTimelineOperation } from "./types";

type Props = {
  workItemIds: string[];
  // a day the timeline shows when it opens, besides its bars and today
  focusDate?: string | null;
  isEditable: boolean;
  showOnlyLeaves: boolean;
  onShowOnlyLeavesChange: (showOnlyLeaves: boolean) => void;
  // saves the place of a work item in the manual order; given when the work items are in that order
  updateSortOrder?: (workItem: TIssue, sortOrder: number) => void;
  updateDates: (updates: IBlockUpdateDependencyData[]) => Promise<void>;
  quickAdd?: ReactNode;
  loadMore?: () => void;
};

const ARROW_KINDS: Record<TTimelineDependencyTypes, TArrowKind> = {
  blocking: "end-start",
  start_before: "start-start",
  finish_before: "end-end",
};

// the distance in the manual order of a line moved to the first or the last place from the line that was there
const SORT_ORDER_STEP = 1000;

/**
 * The timeline of work items. The dates it draws are the stored ones, with the dates a drag is about to give
 * in their place while the drag goes on; an arrow is a conflict when the next work item starts or ends before
 * the day of the previous one that the arrow starts from.
 */
export const WorkItemsTimeline = observer(function WorkItemsTimeline(props: Props) {
  const { workItemIds, showOnlyLeaves, updateSortOrder, updateDates, ...chartProps } = props;
  // router
  const { workspaceSlug, projectId } = useParams();
  // states
  const [previewDates, setPreviewDates] = useState<TSchedule["dates"]>({});
  const [openDependency, setOpenDependency] = useState<TTimelineDependency>();
  // refs
  const previewDatesRef = useRef(previewDates);
  // store hooks
  const {
    issue: { getIssueById },
    rootIssueStore,
  } = useIssueDetail();
  const { getProjectDependencies, fetchDependencies } = useIssuesTimeLineStore();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  // derived values
  const currentProjectRole = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug.toString(), projectId.toString());
  const dependencies = getProjectDependencies(projectId.toString());
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
    if (missingParentIds)
      rootIssueStore.issues.getIssues(workspaceSlug.toString(), projectId.toString(), missingParentIds.split(","));
  }, [missingParentIds, rootIssueStore, workspaceSlug, projectId]);

  useSWR(
    PROJECT_TIMELINE_DEPENDENCIES(projectId.toString(), currentProjectRole),
    () => fetchDependencies(workspaceSlug.toString(), projectId.toString()),
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  // a work item with one date is a task of that one day
  const storedDates: TSchedule["dates"] = {};
  for (const workItemId of workItemIds) {
    const workItem = getIssueById(workItemId);
    const start = workItem?.start_date ?? workItem?.target_date;
    const end = workItem?.target_date ?? workItem?.start_date;
    if (start && end) storedDates[workItemId] = { start, end };
  }
  const dates = { ...storedDates, ...previewDates };

  const arrows: TScheduleArrow[] = dependencies.map((dependency) => ({
    id: dependency.id,
    previousId: dependency.predecessor_id,
    nextId: dependency.dependent_id,
    kind: ARROW_KINDS[dependency.relation_type],
    delay: 0,
  }));
  const conflicts = arrows.flatMap((arrow) => {
    const previous = dates[arrow.previousId];
    const next = dates[arrow.nextId];
    if (!previous || !next) return [];
    const fixedDay = arrow.kind === "end-end" ? next.end : next.start;
    const askedDay = arrow.kind === "start-start" ? previous.start : previous.end;
    return fixedDay < askedDay ? [{ arrowId: arrow.id, fixedDay, askedDay }] : [];
  });
  const schedule: TSchedule = {
    dates,
    decidingArrowId: {},
    conflicts,
    slack: {},
    criticalTaskIds: [],
    criticalArrowIds: [],
  };

  const showPreviewDates = (nextPreviewDates: TSchedule["dates"]) => {
    previewDatesRef.current = nextPreviewDates;
    setPreviewDates(nextPreviewDates);
  };

  const preview = useLatestCallback(({ taskId, edge, day }: TTimelineChange) => {
    const stored = storedDates[taskId] ?? { start: day, end: day };
    const duration = getDayOfDate(stored.end) - getDayOfDate(stored.start);
    // a task is at least one day long
    if (edge === "start") showPreviewDates({ [taskId]: { ...stored, start: day < stored.end ? day : stored.end } });
    else if (edge === "end")
      showPreviewDates({ [taskId]: { ...stored, end: day > stored.start ? day : stored.start } });
    else showPreviewDates({ [taskId]: { start: day, end: getDateOfDay(getDayOfDate(day) + duration) } });
  });

  const commit = useLatestCallback(() => {
    const updates = Object.entries(previewDatesRef.current)
      // a drag that ends on the day it started from changes nothing
      .filter(([id, previewed]) => !isEqual(previewed, storedDates[id]))
      .map(([id, { start, end }]) => ({ id, start_date: start, target_date: end }));
    if (updates.length > 0) updateDates(updates);
    showPreviewDates({});
  });

  const abort = useLatestCallback(() => showPreviewDates({}));

  const operation: TTimelineOperation = useMemo(() => ({ preview, commit, abort }), [preview, commit, abort]);

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
    <>
      <TimelineChart
        taskIds={taskIds}
        arrows={arrows}
        schedule={schedule}
        operation={operation}
        showOnlyLeaves={showOnlyLeaves}
        onLineMove={updateSortOrder && handleLineMove}
        onArrowClick={(arrow) => setOpenDependency(dependencies.find((dependency) => dependency.id === arrow.id))}
        {...chartProps}
      />
      {openDependency && (
        <TimelineRelationModal
          relation={{
            predecessorId: openDependency.predecessor_id,
            dependentId: openDependency.dependent_id,
            dependency: openDependency,
          }}
          isEditable={chartProps.isEditable}
          handleClose={() => setOpenDependency(undefined)}
        />
      )}
    </>
  );
});
