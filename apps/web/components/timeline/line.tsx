/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ComponentProps } from "react";
import { createContext, memo, useContext } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { ALL_ISSUES } from "@plane/constants";
import { ControlLink } from "@plane/blocks/layout";
import type { TTaskEdge } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import { cn, generateWorkItemLink } from "@plane/utils";
// components
import { BLOCK_HEIGHT, SIDEBAR_WIDTH } from "@/components/gantt-chart/constants";
import { IssueIdentifier } from "@/components/issues/issue-detail/issue-identifier";
import { getBlockViewDetails } from "@/components/issues/issue-layouts/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useIssuesStore } from "@/hooks/use-issue-layout-store";
// local imports
import { TimelineBar, TimelineBarText } from "./bar";

type Props = {
  taskId: string;
  lineIndex: number;
  slack: number;
  isFixed: boolean;
  isCritical: boolean;
  isConflictCause: boolean;
  isEditable: boolean;
  isDragged: boolean;
  isStartDated: boolean;
  // how far the line is moved from its place while it is dragged up or down, in pixels
  moveOffset: number | undefined;
  areHandlesShown: boolean;
  linkedEdge: TTaskEdge | undefined;
  isLinkRefused: boolean;
  onBarPress: (press: React.PointerEvent, taskId: string, edge?: TTaskEdge) => void;
  onHandlePress: (press: React.PointerEvent, taskId: string, edge: TTaskEdge) => void;
  onEntryPress: (press: React.PointerEvent, taskId: string) => void;
  onClick: (click: React.MouseEvent, taskId: string) => void;
};

/**
 * The first and the last day of every task that has a bar; a task that is not on the timeline has none. The bar
 * of a line and the days it lasts are drawn from here, not from what the line is given: a preview that moves
 * bars then draws nothing else of their lines again.
 */
export const TimelineDaysContext = createContext<Record<string, { start: number; end: number } | undefined>>({});

const DurationText = memo(function DurationText(props: { days: number }) {
  // translation
  const { t } = useTranslation();

  return <span className="shrink-0 text-13 text-secondary">{t("workspace_projects.common.days_count", props)}</span>;
});

function LineDuration(props: { taskId: string }) {
  const task = useContext(TimelineDaysContext)[props.taskId];

  return task ? <DurationText days={task.end - task.start + 1} /> : null;
}

function LineBar(props: Omit<ComponentProps<typeof TimelineBar>, "start" | "end">) {
  const task = useContext(TimelineDaysContext)[props.taskId];

  return task ? <TimelineBar start={task.start} end={task.end} {...props} /> : null;
}

/** The line of a task: its entry in the list at the left, and its bar on the timeline when it has dates. */
export const TimelineLine = observer(function TimelineLine(props: Props) {
  const { taskId, lineIndex, moveOffset, onBarPress, onEntryPress, onClick, ...barProps } = props;
  // router
  const { workspaceSlug } = useParams();
  // store hooks
  const {
    issue: { getIssueById },
    getIsIssuePeeked,
  } = useIssueDetail();
  const { getIsRowSelected } = useListView();
  const { getProjectIdentifierById } = useProject();
  const { getStateById } = useProjectState();
  const { issuesFilter } = useIssuesStore();
  // derived values
  const issue = getIssueById(taskId);
  const isSelected = getIsRowSelected(taskId, ALL_ISSUES);
  const cellClassName = cn("group-hover/line:bg-layer-transparent-hover", {
    "bg-layer-transparent-selected group-hover/line:bg-layer-transparent-selected": isSelected,
  });

  if (!issue?.project_id) return null;

  const workItemLink = generateWorkItemLink({
    workspaceSlug: workspaceSlug?.toString(),
    projectId: issue.project_id,
    issueId: taskId,
    projectIdentifier: getProjectIdentifierById(issue.project_id),
    sequenceId: issue.sequence_id,
  });
  const stateColor = getStateById(issue.state_id)?.color ?? "";

  return (
    <div
      // a press on the work item that is open beside the timeline does not close it
      id={`issue-${taskId}`}
      // a line that is moved goes with the pointer, entry and bar together, above the other lines
      className={cn("group/line absolute inset-x-0 flex", {
        "z-[3] bg-surface-1 shadow-raised-200": moveOffset !== undefined,
      })}
      style={{
        top: lineIndex * BLOCK_HEIGHT,
        height: BLOCK_HEIGHT,
        transform: moveOffset === undefined ? undefined : `translateY(${moveOffset}px)`,
      }}
    >
      <ControlLink
        href={workItemLink}
        className={cn("flex shrink-0 cursor-pointer items-center gap-2 px-page-x", cellClassName, {
          "rounded-l-sm border border-r-0 border-accent-strong": getIsIssuePeeked(taskId),
        })}
        style={{ width: SIDEBAR_WIDTH }}
        disabled={!!issue.tempId}
        onPointerDown={(e) => onEntryPress(e, taskId)}
        onClick={(e) => onClick(e, taskId)}
      >
        <IssueIdentifier
          issueId={taskId}
          projectId={issue.project_id}
          size="xs"
          variant="tertiary"
          displayProperties={issuesFilter?.issueFilters?.displayProperties}
        />
        <span className="grow truncate text-13 font-medium text-primary">{issue.name}</span>
        <LineDuration taskId={taskId} />
      </ControlLink>
      <div className={cn("relative min-w-0 grow overflow-hidden", cellClassName)}>
        <LineBar
          taskId={taskId}
          href={workItemLink}
          color={stateColor}
          // a work item with one date fades towards the side of the date it lacks
          style={getBlockViewDetails(issue, stateColor).blockStyle}
          isSelected={isSelected}
          isDisabled={!!issue.tempId}
          onPress={onBarPress}
          onClick={onClick}
          {...barProps}
        >
          <TimelineBarText taskId={taskId} />
        </LineBar>
      </div>
    </div>
  );
});
