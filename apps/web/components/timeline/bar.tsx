/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { CSSProperties, ReactNode } from "react";
import { memo, useContext } from "react";
import { observer } from "mobx-react";
// plane imports
import { ControlLink } from "@plane/blocks/layout";
import { getPillButtonClassName } from "@plane/blocks/pill-button";
import type { TTaskEdge } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import type { TIssue } from "@plane/types";
import { cn, getTextFromHTML, renderFormattedDate } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useLabel } from "@/hooks/store/use-label";
// local imports
import { getDateOfDay, getDayX, MIN_BAR_WIDTH, TimelineViewContext } from "./scale";

type Props = {
  taskId: string;
  // the page of the work item
  href: string;
  // the first and the last day of the task
  start: number;
  end: number;
  // the days the task can slip without moving the end of its group
  slack: number;
  // the colour of the bar, and of the tail that shows the slack
  color: string;
  style: CSSProperties;
  // its start is a day; else it follows its arrows
  isFixed: boolean;
  isCritical: boolean;
  // it is among the tasks that produce the conflict the pointer is over
  isConflictCause: boolean;
  isSelected: boolean;
  isEditable: boolean;
  isDragged: boolean;
  // the day of its start shows beside it: it is fixed on that day and an arrow leads to it
  isStartDated: boolean;
  isDisabled: boolean;
  // an arrow is being drawn, so every bar shows its handles
  areHandlesShown: boolean;
  // the handle that holds the arrow that is being made: one that is drawn to it, or the one that a task dragged
  // from the list follows; and whether it takes the arrow
  linkedEdge: TTaskEdge | undefined;
  isLinkRefused: boolean;
  onPress: (press: React.PointerEvent, taskId: string, edge?: TTaskEdge) => void;
  onHandlePress: (press: React.PointerEvent, taskId: string, edge: TTaskEdge) => void;
  onClick: (click: React.MouseEvent, taskId: string) => void;
  // the text of the bar
  children: ReactNode;
};

// where a bar is in its line
export const BAR_TOP = 6;
export const BAR_HEIGHT = 32;
// A date beside a bar stands this far from it, clear of the handle there and of the end of an arrow, and is about
// this wide.
export const DATE_DISTANCE = 28;
export const DATE_WIDTH = 86;
const TEXT_PADDING = 10;
// the look of what stands around a bar while it is dragged: its dates, and the days it lasts
export const MARKER_CLASS_NAME =
  "pointer-events-none rounded-sm bg-accent-subtle px-2 py-1 text-11 whitespace-nowrap text-tertiary";
const DATE_CLASS_NAME = cn(MARKER_CLASS_NAME, "absolute top-1/2 -translate-y-1/2");

/**
 * The handles at the start and the end of a bar: an arrow is drawn from one to one of another bar. They show
 * while the pointer is over the bar and while an arrow is drawn, and the one that holds an arrow that is being
 * made shows whatever else. A bar that moves does not draw them again.
 */
const BarHandles = memo(function BarHandles(
  props: Pick<Props, "taskId" | "areHandlesShown" | "linkedEdge" | "isLinkRefused" | "onHandlePress">
) {
  const { taskId, areHandlesShown, linkedEdge, isLinkRefused, onHandlePress } = props;
  // translation
  const { t } = useTranslation();

  return (["start", "end"] as const).map((edge) => (
    <button
      key={edge}
      type="button"
      aria-label={t(`timeline.handle.${edge}`)}
      className={cn(
        "absolute top-1/2 size-2.5 -translate-y-1/2 cursor-crosshair rounded-full border-2 border-accent-strong bg-surface-1 opacity-0 group-hover/bar:opacity-100",
        edge === "start" ? "-left-3.5" : "-right-3.5",
        {
          "opacity-100": areHandlesShown || linkedEdge === edge,
          "scale-150 bg-accent-primary": linkedEdge === edge && !isLinkRefused,
          "scale-150 border-danger-strong bg-danger-primary": linkedEdge === edge && isLinkRefused,
        }
      )}
      onPointerDown={(e) => onHandlePress(e, taskId, edge)}
    />
  ));
});

/**
 * The bar of a task. It is drawn again at every change of the view, so it holds no more than its place: its text
 * comes ready from the line of the task, which a change of the view leaves alone.
 */
export const TimelineBar = memo(function TimelineBar(props: Props) {
  const {
    taskId,
    href,
    start,
    end,
    slack,
    color,
    style,
    isFixed,
    isCritical,
    isConflictCause,
    isSelected,
    isEditable,
    isDragged,
    isStartDated,
    isDisabled,
    areHandlesShown,
    linkedEdge,
    isLinkRefused,
    onPress,
    onHandlePress,
    onClick,
    children,
  } = props;
  // context
  const view = useContext(TimelineViewContext);
  // derived values
  const left = getDayX(view, start);
  const width = Math.max(getDayX(view, end + 1) - left, MIN_BAR_WIDTH);
  const slackWidth = getDayX(view, end + 1 + slack) - getDayX(view, end + 1);
  const isInView = left < view.width && left + width + slackWidth > 0;

  return (
    <div
      className="group/bar absolute z-[2]"
      // out of view it is not laid out, so a change of the view costs nothing for it
      style={isInView ? { left, width, top: BAR_TOP, height: BAR_HEIGHT } : { display: "none" }}
    >
      {slack > 0 && (
        <div
          // a press on it goes to what is under it: the end of an arrow is taken there
          className="pointer-events-none absolute top-1/2 left-full h-1.5 -translate-y-1/2 rounded-r-full opacity-40"
          style={{ width: slackWidth, backgroundColor: color }}
        />
      )}
      <ControlLink
        href={href}
        className={cn("relative block h-full w-full cursor-pointer overflow-hidden rounded-sm text-primary", {
          "ring-2 ring-accent-strong": isCritical,
          "ring-2 ring-danger-strong": isConflictCause,
          "outline-2 outline-offset-1 outline-current": isSelected,
        })}
        style={style}
        disabled={isDisabled}
        onPointerDown={(e) => onPress(e, taskId)}
        onClick={(e) => onClick(e, taskId)}
      >
        <div className="absolute inset-0 bg-surface-1/50" />
        {/* a fixed task has a firm start; the start of a task that follows its arrows is where an arrow puts it */}
        {isFixed && <div className="absolute inset-y-0 left-0 w-[3px] bg-current opacity-60" />}
        <div
          className="relative flex h-full items-center whitespace-pre"
          style={{
            // the text stays in the part of the bar that is in view
            paddingLeft: Math.max(-left, 0) + TEXT_PADDING,
            paddingRight: Math.max(left + width - view.width, 0) + TEXT_PADDING,
          }}
        >
          {children}
        </div>
      </ControlLink>
      {isEditable && (
        <>
          <div
            className="absolute inset-y-0 -left-1 w-2 cursor-col-resize"
            onPointerDown={(e) => onPress(e, taskId, "start")}
          />
          <div
            className="absolute inset-y-0 -right-1 w-2 cursor-col-resize"
            onPointerDown={(e) => onPress(e, taskId, "end")}
          />
        </>
      )}
      {isEditable && (
        <BarHandles
          taskId={taskId}
          areHandlesShown={areHandlesShown}
          linkedEdge={linkedEdge}
          isLinkRefused={isLinkRefused}
          onHandlePress={onHandlePress}
        />
      )}
      {(isDragged || isStartDated) && (
        <div className={cn(DATE_CLASS_NAME, "right-full")} style={{ marginRight: DATE_DISTANCE }}>
          {renderFormattedDate(getDateOfDay(start))}
        </div>
      )}
      {isDragged && (
        <div className={cn(DATE_CLASS_NAME, "left-full")} style={{ marginLeft: DATE_DISTANCE }}>
          {renderFormattedDate(getDateOfDay(end))}
        </div>
      )}
    </div>
  );
});

/** The loaded work items a work item is under, the topmost first. */
export const getParents = (issue: TIssue, getIssueById: (issueId: string) => TIssue | undefined) => {
  const parents: TIssue[] = [];
  // the API accepts a parent that is under its own sub-work item, so a work item is looked at once
  const seenIds = new Set([issue.id]);
  let parent = issue.parent_id ? getIssueById(issue.parent_id) : undefined;
  while (parent && !seenIds.has(parent.id)) {
    seenIds.add(parent.id);
    parents.unshift(parent);
    parent = parent.parent_id ? getIssueById(parent.parent_id) : undefined;
  }
  return parents;
};

// A part of the text of a bar that goes when the bar is too short. What is in it and does not fit moves to a
// second line, which is not shown: a label goes whole, the description once too little of it is left to read.
const PART_CLASS_NAME = "flex h-5 min-w-0 flex-wrap content-start items-center overflow-hidden before:h-full";

/**
 * The text of a bar: `parent / parent / name  description  labels`. A bar too short for all of it loses the
 * description first, then the parents, then the labels; the name is cut last. The parts shrink one after the
 * other because each shrinks so much more readily than the next that the next does not lose a pixel meanwhile.
 */
export const TimelineBarText = observer(function TimelineBarText(props: { taskId: string }) {
  const { taskId } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getLabelById } = useLabel();
  // derived values
  const issue = getIssueById(taskId);

  if (!issue) return null;

  const parents = getParents(issue, getIssueById);
  const description = issue.description_prefix && getTextFromHTML(issue.description_prefix);
  const labels = issue.label_ids.map((labelId) => getLabelById(labelId)).filter((label) => !!label);

  return (
    <>
      {parents.length > 0 && (
        // cut at its start, so that the nearest parent is the last to go
        <span
          dir="rtl"
          className="min-w-0 shrink-[1000000000000] overflow-hidden text-body-xs-regular text-ellipsis text-secondary"
        >
          <bdi>{parents.map((parent) => `${parent.name} / `).join("")}</bdi>
        </span>
      )}
      <span className="min-w-0 truncate text-body-xs-medium">{issue.name}</span>
      {description && (
        <span className={cn(PART_CLASS_NAME, "shrink-[1000000000000000000]")}>
          <span className="min-w-12 grow basis-12 overflow-hidden text-caption-md-regular text-ellipsis text-secondary">
            {`  ${description}`}
          </span>
        </span>
      )}
      {labels.length > 0 && (
        <span className={cn(PART_CLASS_NAME, "shrink-[1000000] gap-x-1 before:w-1")}>
          {labels.map((label) => (
            <span key={label.id} className={cn(getPillButtonClassName("sm"), "max-w-40 shrink-0")}>
              <span className="block size-2 shrink-0 rounded-full" style={{ backgroundColor: label.color }} />
              <span className="truncate">{label.name}</span>
            </span>
          ))}
        </span>
      )}
    </>
  );
});
