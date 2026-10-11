/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TArrowDelay, TArrowKind, TDay, TSchedule, TScheduleArrow, TScheduleTask } from "./types";

/** A day of January 2026. */
export const day = (dayOfMonth: number): TDay => `2026-01-${String(dayOfMonth).padStart(2, "0")}`;

export const fixed = (id: string, dayOfMonth: number, duration: number): TScheduleTask => ({
  id,
  duration,
  start: { at: day(dayOfMonth) },
});

export const following = (id: string, duration: number): TScheduleTask => ({ id, duration, start: "anchor" });

/** An arrow named by its tasks, "A>B" from A to B; the name is its id. */
export const arrow = (name: string, kind: TArrowKind, delay: TArrowDelay = 0): TScheduleArrow => {
  const [previousId, nextId] = name.split(">");
  return { id: name, previousId, nextId, kind, delay };
};

/** The dates of tasks, each written as the days of January 2026 it starts and ends on. */
export const dates = (days: Record<string, [number, number]>): TSchedule["dates"] =>
  Object.fromEntries(Object.entries(days).map(([id, [start, end]]) => [id, { start: day(start), end: day(end) }]));

/** A schedule in which nothing is decided, asked, in conflict, able to slip or critical. */
export const PLAIN_SCHEDULE: TSchedule = {
  dates: {},
  decidingArrowId: {},
  gaps: {},
  conflicts: [],
  apartLinks: [],
  slack: {},
  criticalTaskIds: [],
  criticalArrowIds: [],
};
