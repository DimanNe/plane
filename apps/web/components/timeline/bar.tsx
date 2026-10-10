/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { CSSProperties, ReactNode } from "react";
import { useContext } from "react";
import { observer } from "mobx-react";
// plane imports
import { ControlLink } from "@plane/blocks/layout";
import { getPillButtonClassName } from "@plane/blocks/pill-button";
import type { TIssue } from "@plane/types";
import { cn, getTextFromHTML, renderFormattedDate } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useLabel } from "@/hooks/store/use-label";
// local imports
import { getDateOfDay, getDayX, MIN_BAR_WIDTH, TimelineViewContext } from "./scale";

export type TBarEdge = "start" | "end";

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
  isCritical: boolean;
  isSelected: boolean;
  isEditable: boolean;
  isDragged: boolean;
  isDisabled: boolean;
  onPress: (press: React.PointerEvent, taskId: string, edge?: TBarEdge) => void;
  onClick: (click: React.MouseEvent, taskId: string) => void;
  renderHandle?: (taskId: string, edge: TBarEdge) => ReactNode;
  // the text of the bar
  children: ReactNode;
};

const TEXT_PADDING = 10;
const DATE_CLASS_NAME =
  "absolute top-1/2 -translate-y-1/2 rounded-sm bg-accent-subtle px-2 py-1 text-11 whitespace-nowrap text-tertiary";

/**
 * The bar of a task. It is drawn again at every change of the view, so it holds no more than its place: its text
 * comes ready from the line of the task, which a change of the view leaves alone.
 */
export function TimelineBar(props: Props) {
  const {
    taskId,
    href,
    start,
    end,
    slack,
    color,
    style,
    isCritical,
    isSelected,
    isEditable,
    isDragged,
    isDisabled,
    onPress,
    onClick,
    renderHandle,
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
      className="group/bar absolute top-1.5 z-[2] h-8"
      // out of view it is not laid out, so a change of the view costs nothing for it
      style={isInView ? { left, width } : { display: "none" }}
    >
      {slack > 0 && (
        <div
          className="absolute top-1/2 left-full h-1.5 -translate-y-1/2 rounded-r-full opacity-40"
          style={{ width: slackWidth, backgroundColor: color }}
        />
      )}
      <ControlLink
        href={href}
        className={cn("relative block h-full w-full cursor-pointer overflow-hidden rounded-sm text-primary", {
          "ring-2 ring-accent-strong": isCritical,
          "outline-2 outline-offset-1 outline-current": isSelected,
        })}
        style={style}
        disabled={isDisabled}
        onPointerDown={(e) => onPress(e, taskId)}
        onClick={(e) => onClick(e, taskId)}
      >
        <div className="absolute inset-0 bg-surface-1/50" />
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
      {renderHandle && (
        <>
          <div className="absolute top-1/2 right-full -translate-y-1/2">{renderHandle(taskId, "start")}</div>
          <div className="absolute top-1/2 left-full -translate-y-1/2">{renderHandle(taskId, "end")}</div>
        </>
      )}
      {isDragged && (
        <>
          <div className={cn(DATE_CLASS_NAME, "right-full mr-2")}>{renderFormattedDate(getDateOfDay(start))}</div>
          <div className={cn(DATE_CLASS_NAME, "left-full ml-2")}>{renderFormattedDate(getDateOfDay(end))}</div>
        </>
      )}
    </div>
  );
}

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
