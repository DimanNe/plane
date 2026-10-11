/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { memo, useState } from "react";
// plane imports
import { getArrowMode, getLatestArrowId, moveTask, resizeTask } from "@plane/blocks/timeline-schedule";
import type { TPlan, TSchedule } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import { cn, renderFormattedDate } from "@plane/utils";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import { getArrowModeParts } from "./arrow-parts";
import type { TTextPart } from "./arrow-parts";
import type { TArrowWaysProps } from "./arrows";
import { getArrowLayerStyle } from "./arrows";
import { DATE_DISTANCE } from "./bar";
import type { TTimelineView } from "./scale";
import { getDateOfDay, getDayDistance, MIN_BAR_WIDTH } from "./scale";
import { TimelineTurnedText } from "./turned-text";
import type { TWheelTurn } from "./use-wheel-turn";

type Props = Pick<TArrowWaysProps, "days" | "lineIndexes" | "firstLine" | "lastLine" | "pxPerDay"> & {
  plan: TPlan;
  schedule: TSchedule;
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
    plan,
    schedule,
    datedTaskIds,
    shownTaskId,
    wheelTurn,
    isEditable,
    onHover,
  } = props;
  // states
  // The start that the pointer is on, and the arrow that it tells of. The wheel there may turn that arrow so that
  // its task follows it again: the text then tells what the arrow has become, for as long as the pointer is on it.
  const [heldStart, setHeldStart] = useState<{ taskId: string; arrowId: string | undefined }>();
  // translation
  const { t } = useTranslation();
  // derived values
  const taskIds = new Set([
    ...datedTaskIds,
    ...(shownTaskId ? [shownTaskId] : []),
    ...(heldStart ? [heldStart.taskId] : []),
  ]);

  return [...taskIds].flatMap((taskId) => {
    const task = days[taskId];
    const lineIndex = lineIndexes.get(taskId);
    if (!task || lineIndex === undefined || lineIndex < firstLine - 1 || lineIndex > lastLine) return [];
    const startX = getDayDistance(pxPerDay, task.start);
    const endX = Math.max(getDayDistance(pxPerDay, task.end + 1), startX + MIN_BAR_WIDTH);
    const formatDay = (day: number) => renderFormattedDate(getDateOfDay(day)) ?? "";
    // Of a task that is fixed on its day and to which arrows lead, the start says so, "on" and the day, for the
    // arrow that asks for the latest day: that one decides where the task stands when it follows again.
    const arrowId =
      heldStart?.taskId === taskId
        ? heldStart.arrowId
        : datedTaskIds.has(taskId)
          ? getLatestArrowId(plan.arrows, schedule, taskId)
          : undefined;
    const arrow = arrowId ? plan.arrows.find((other) => other.id === arrowId) : undefined;
    // What a notch of the wheel does on each date, a day later for a notch up: the start takes the task with
    // it, as a drag of its bar does; the end leaves the start where it is, as a drag of that edge does.
    const parts: Record<"start" | "end", TTextPart[]> = {
      start: arrow
        ? getArrowModeParts(arrow, getArrowMode(plan, arrow), task.start, t)
        : [
            {
              key: "value",
              label: formatDay(task.start),
              turn: (turned, direction) => moveTask(turned, taskId, getDateOfDay(task.start + direction)),
            },
          ],
      end: [
        {
          key: "value",
          label: formatDay(task.end),
          turn: (turned, direction) => resizeTask(turned, taskId, "end", getDateOfDay(task.end + direction)),
        },
      ],
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
        parts={isEditable ? parts[edge] : parts[edge].map(({ key, label }) => ({ key, label }))}
        turnKey={`${taskId} ${edge}`}
        wheelTurn={wheelTurn}
        onHover={(isOver) => {
          if (edge === "start") setHeldStart(isOver ? { taskId, arrowId } : undefined);
          onHover(isOver ? taskId : undefined);
        }}
      />
    ));
  });
});

/**
 * The dates beside the bars: where a bar starts and ends is read off the header only roughly, and of a task that
 * is fixed on its day that day is what the plan says about it: "on" and the day. A date is also where it is
 * changed most exactly: the wheel on it moves it by a day, and the wheel on "on" lets the task follow its arrow.
 */
export function TimelineDateMarkers(props: Omit<Props, "pxPerDay"> & { view: TTimelineView }) {
  const { view, ...markersProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getArrowLayerStyle(view)}>
      <DateMarkers pxPerDay={view.pxPerDay} {...markersProps} />
    </div>
  );
}
