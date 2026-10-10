/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// What the scheduling function hands to the timeline. Days are YYYY-MM-DD; a task's end is its last day.
export type TArrowKind = "end-start" | "start-start" | "end-end";

export type TScheduleArrow = {
  id: string;
  previousId: string;
  nextId: string;
  kind: TArrowKind;
  // days, 0 = immediately
  delay: number;
};

export type TConflict = { arrowId: string; fixedDay: string; askedDay: string };

export type TSchedule = {
  dates: Record<string, { start: string; end: string }>;
  // the arrow that decides a computed task's start
  decidingArrowId: Record<string, string | undefined>;
  conflicts: TConflict[];
  slack: Record<string, number>;
  criticalTaskIds: string[];
  criticalArrowIds: string[];
};

/** Where a drag takes a task: the whole task to a start day, or one of its edges to a day. */
export type TTimelineChange = { taskId: string; edge?: "start" | "end"; day: string };

/** One operation on the timeline: shown while the pointer moves, then saved or dropped. */
export type TTimelineOperation = {
  preview: (change: TTimelineChange) => void;
  commit: () => void;
  abort: () => void;
};
