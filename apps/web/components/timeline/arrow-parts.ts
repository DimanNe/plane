/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { changeArrow, getDelayDays, moveTask, turnArrowMode } from "@plane/blocks/timeline-schedule";
import type { TArrowMode, TPlan, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { renderFormattedDate } from "@plane/utils";
// local imports
import { getDateOfDay } from "./scale";

/**
 * A part of a text of the chart: what it is of the text, what it says, and what a notch of the wheel on it
 * changes. A part without that only tells.
 */
export type TTextPart = {
  key: "mode" | "value";
  label: string;
  turn?: (plan: TPlan, direction: 1 | -1) => TPlan;
};

type TTranslate = (key: string, params?: Record<string, unknown>) => string;

/**
 * The text that tells how an arrow holds its next task, in parts: "linked"; "in" and "n d"; "on" and the day
 * the task is fixed on. The first part is what the arrow is, and the wheel on it turns that. The second is the
 * number that goes with it, and the wheel on it changes the number: the days of "in n d", the day of "on".
 */
export const getArrowModeParts = (
  arrow: TScheduleArrow,
  mode: TArrowMode,
  // the first day of the next task
  nextStart: number,
  t: TTranslate
): Required<TTextPart>[] => {
  const modePart = {
    key: "mode" as const,
    label: t(`timeline.arrow.${mode}`),
    turn: (plan: TPlan, direction: 1 | -1) => turnArrowMode(plan, arrow.id, direction),
  };
  if (mode === "linked") return [modePart];
  if (mode === "on")
    return [
      modePart,
      {
        key: "value",
        label: renderFormattedDate(getDateOfDay(nextStart)) ?? "",
        turn: (plan, direction) => moveTask(plan, arrow.nextId, getDateOfDay(nextStart + direction)),
      },
    ];
  const days = getDelayDays(arrow.delay);
  return [
    modePart,
    {
      key: "value",
      label: t("timeline.duration", { days }),
      turn: (plan, direction) => changeArrow(plan, arrow.id, { delay: Math.max(days + direction, 0) }),
    },
  ];
};
