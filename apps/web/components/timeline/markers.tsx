/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { memo } from "react";
// plane imports
import { moveTask, resizeTask } from "@plane/blocks/timeline-schedule";
import type { TPlan } from "@plane/blocks/timeline-schedule";
import { cn, renderFormattedDate } from "@plane/utils";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import type { TArrowWaysProps } from "./arrows";
import { getArrowLayerStyle } from "./arrows";
import { DATE_DISTANCE } from "./bar";
import type { TTimelineView } from "./scale";
import { getDateOfDay, getDayDistance, MIN_BAR_WIDTH } from "./scale";
import { TimelineTurnedText } from "./turned-text";
import type { TWheelTurn } from "./use-wheel-turn";

type Props = Pick<TArrowWaysProps, "days" | "lineIndexes" | "firstLine" | "lastLine" | "pxPerDay"> & {
  // the fixed tasks to which an arrow leads: their start shows always, because the arrow does not tell it
  datedTaskIds: Set<string>;
  // the task whose bar is under the pointer, or is dragged: both its dates show
  shownTaskId: string | undefined;
  wheelTurn: TWheelTurn;
  isEditable: boolean;
  // the pointer is on a date of the task, which is as good as on its bar
  onHover: (taskId: string | undefined) => void;
};

const DateMarkers = memo(function DateMarkers(props: Props) {
  const {
    days,
    lineIndexes,
    firstLine,
    lastLine,
    pxPerDay,
    datedTaskIds,
    shownTaskId,
    wheelTurn,
    isEditable,
    onHover,
  } = props;
  // derived values
  const taskIds = shownTaskId && !datedTaskIds.has(shownTaskId) ? [...datedTaskIds, shownTaskId] : [...datedTaskIds];

  return taskIds.flatMap((taskId) => {
    const task = days[taskId];
    const lineIndex = lineIndexes.get(taskId);
    if (!task || lineIndex === undefined || lineIndex < firstLine - 1 || lineIndex > lastLine) return [];
    const startX = getDayDistance(pxPerDay, task.start);
    const endX = Math.max(getDayDistance(pxPerDay, task.end + 1), startX + MIN_BAR_WIDTH);
    // What a notch of the wheel does on each date, a day later for a notch up: the start takes the task with
    // it, as a drag of its bar does; the end leaves the start where it is, as a drag of that edge does.
    const changes = {
      start: (plan: TPlan, direction: 1 | -1) => moveTask(plan, taskId, getDateOfDay(task.start + direction)),
      end: (plan: TPlan, direction: 1 | -1) => resizeTask(plan, taskId, "end", getDateOfDay(task.end + direction)),
    };
    return (taskId === shownTaskId ? (["start", "end"] as const) : (["start"] as const)).map((edge) => (
      <TimelineTurnedText
        key={`${taskId} ${edge}`}
        place={{
          className: cn("absolute -translate-y-1/2", { "-translate-x-full": edge === "start" }),
          style: {
            left: edge === "start" ? startX - DATE_DISTANCE : endX + DATE_DISTANCE,
            top: (lineIndex + 0.5) * BLOCK_HEIGHT,
          },
        }}
        turn={isEditable ? { key: `${taskId} ${edge}`, change: changes[edge] } : undefined}
        wheelTurn={wheelTurn}
        onHover={(isOver) => onHover(isOver ? taskId : undefined)}
      >
        {renderFormattedDate(getDateOfDay(task[edge]))}
      </TimelineTurnedText>
    ));
  });
});

/**
 * The dates beside the bars: where a bar starts and ends is read off the header only roughly, and of a task that
 * is fixed on its day that day is what the plan says about it. A date is also where it is changed most exactly:
 * the wheel on it moves it by a day.
 */
export function TimelineDateMarkers(props: Omit<Props, "pxPerDay"> & { view: TTimelineView }) {
  const { view, ...markersProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getArrowLayerStyle(view)}>
      <DateMarkers pxPerDay={view.pxPerDay} {...markersProps} />
    </div>
  );
}
