/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/** A day is written YYYY-MM-DD, as Plane's start and due dates are. */
export type TDay = string;

export type TTaskEdge = "start" | "end";

/** From which edge of the previous task to which edge of the next one. Start to end does not exist. */
export type TArrowKind = "end-start" | "start-start" | "end-end";

/** A fixed task stays on its day; an "anchor" task starts where its incoming arrows ask. */
export type TTaskStart = { at: TDay } | "anchor";

/** `duration` in days, at least 1: a task that starts and ends on the same day lasts 1. */
export type TScheduleTask = { id: string; duration: number; start: TTaskStart };

/** `delay` in days between the anchor and the edge of the next task that the arrow constrains, 0 = immediately. */
export type TScheduleArrow = { id: string; previousId: string; nextId: string; kind: TArrowKind; delay: number };

export type TPlan = { tasks: TScheduleTask[]; arrows: TScheduleArrow[] };

export type TWayOut =
  | { way: "follow-arrows" }
  | { way: "move-fixed-day"; day: TDay }
  | { way: "shorten-delay"; delay: number }
  | { way: "remove-arrow" };

/** An arrow that asks its fixed next task to start later than the day it is fixed on. */
export type TConflict = {
  arrowId: string;
  taskId: string;
  fixedDay: TDay;
  /** the start that the arrow asks for */
  askedDay: TDay;
  /** the previous task's start (start -> start) or end, from which the arrow counts its delay */
  anchorDay: TDay;
  /** "shorten-delay" is among them only when that alone ends this conflict */
  waysOut: TWayOut[];
};

export type TSchedule = {
  dates: Record<string, { start: TDay; end: TDay }>;
  /** of a task that follows its arrows: the arrow that asks for the latest start */
  decidingArrowId: Record<string, string | undefined>;
  /** per arrow: the delay it would have if it asked for exactly where its next task stands */
  gaps: Record<string, number>;
  conflicts: TConflict[];
  /** days a task can slip, for the tasks of a group of more than two tasks connected by arrows */
  slack: Record<string, number>;
  criticalTaskIds: string[];
  criticalArrowIds: string[];
};

export type TRefusal = { refused: "same-task" | "already-connected" | "loop" };
