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

/**
 * What an arrow asks of the edge of its next task that it constrains. "linked" keeps that edge together with the
 * edge the arrow leads from, whichever of the two tasks is moved. A number is "in n d", from 0 up: the edge
 * stands that many days after the other, and moving the next task changes the number. "in 0 d" and "linked" put
 * the task on the same day and are different things.
 */
export type TArrowDelay = number | "linked";

export type TScheduleArrow = { id: string; previousId: string; nextId: string; kind: TArrowKind; delay: TArrowDelay };

/** How an arrow holds its next task: linked to it, in n d, or not at all because the task is fixed on its day. */
export type TArrowMode = "linked" | "in" | "on";

export type TPlan = { tasks: TScheduleTask[]; arrows: TScheduleArrow[] };

/**
 * What a move of a task comes to: the plan after it, and the arrows that stop it. An arrow stops a move when the
 * task was asked to go further than the arrow lets its body go; it tells why the bar stays behind the pointer.
 */
export type TTaskMove = { plan: TPlan; stoppingArrowIds: string[] };

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

/**
 * A linked arrow whose edges are not together: another arrow holds its next task `days` later than the link
 * asks. Linked says that the two tasks move as one, and the plan does not keep that here.
 */
export type TApartLink = { arrowId: string; taskId: string; days: number; heldByArrowId: string };

export type TSchedule = {
  dates: Record<string, { start: TDay; end: TDay }>;
  /** of a task that follows its arrows: the arrow that asks for the latest start */
  decidingArrowId: Record<string, string | undefined>;
  /** per arrow: the delay it would have if it asked for exactly where its next task stands */
  gaps: Record<string, number>;
  conflicts: TConflict[];
  apartLinks: TApartLink[];
  /** days a task can slip, for the tasks of a group of more than two tasks connected by arrows */
  slack: Record<string, number>;
  criticalTaskIds: string[];
  criticalArrowIds: string[];
};

export type TRefusal = { refused: "same-task" | "already-connected" | "loop" };
