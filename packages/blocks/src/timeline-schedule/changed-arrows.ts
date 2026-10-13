/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TPlan, TSchedule } from "./types";

/**
 * The arrows that an operation has changed, given the plan it began with and the plan it has come to: an arrow
 * that asks for something else than it did, "linked" or the n of "in n d"; an arrow of another length, the days
 * between the two edges it joins; and a new arrow. An arrow whose two tasks went later by the same days is pushed,
 * not changed: it asks what it asked and is as long as it was.
 */
export const getChangedArrowIds = (
  before: { plan: TPlan; schedule: TSchedule },
  after: { plan: TPlan; schedule: TSchedule }
): string[] => {
  const delaysBefore = new Map(before.plan.arrows.map((arrow) => [arrow.id, arrow.delay]));
  return after.plan.arrows.flatMap((arrow) =>
    delaysBefore.get(arrow.id) === arrow.delay && before.schedule.gaps[arrow.id] === after.schedule.gaps[arrow.id]
      ? []
      : [arrow.id]
  );
};
