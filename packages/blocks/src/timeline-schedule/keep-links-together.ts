/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { computeSchedule } from "./compute-schedule";
import { toDay, toDayNumber } from "./days";
import { getTaskMove } from "./gestures";
import type { TPlan, TSchedule } from "./types";

/** The links of a plan whose two edges are together. An arrow into a task that is fixed on its day is a check. */
const getLinkIdsTogether = (plan: TPlan): Set<string> => {
  const { gaps, decidingArrowId } = computeSchedule(plan.tasks, plan.arrows);
  return new Set(
    plan.arrows.flatMap((arrow) =>
      arrow.delay === "linked" && gaps[arrow.id] === 0 && decidingArrowId[arrow.nextId] ? [arrow.id] : []
    )
  );
};

/**
 * No operation of the timeline makes a link come apart: an arrow that is linked before and after the operation,
 * and whose two edges were together before it, has them together after it. Takes the plan an operation began
 * with and the plan the operation gives, and returns the plan to show and to save, with its schedule.
 *
 * A gesture moves the body of the task it changes, and what follows from outside follows as the plan computes.
 * A task that is pushed in this way can leave a link that leads to it from a task that stayed. The task the
 * link leads from then goes later by the days the link is apart, with its body, as `getTaskMove` moves a body.
 * That can push further tasks and open further links, so it goes on until no such link is left.
 *
 * Arrows can form a round that no move later closes: the body that goes later to meet a task pushes that task
 * on. In a plan whose links can all be kept, no task has to go later by more than the days these links are apart
 * right after the operation, added up, so a task that is asked to go further is taken to be on a round. The
 * operation's own plan is returned then: the link is apart in it and shows its ways out.
 */
export function keepLinksTogether(before: TPlan, after: TPlan): { plan: TPlan; schedule: TSchedule } {
  const computed = { plan: after, schedule: computeSchedule(after.tasks, after.arrows) };
  if (computed.schedule.apartLinks.length === 0) return computed;
  const keptIds = getLinkIdsTogether(before);
  const getApartLink = ({ apartLinks }: TSchedule) => apartLinks.find(({ arrowId }) => keptIds.has(arrowId));
  const previousIds = Object.fromEntries(after.arrows.map((arrow) => [arrow.id, arrow.previousId]));
  const mostDays = computed.schedule.apartLinks.reduce(
    (days, link) => days + (keptIds.has(link.arrowId) ? link.days : 0),
    0
  );

  let kept = computed;
  for (let link = getApartLink(kept.schedule); link; link = getApartLink(kept.schedule)) {
    const previousId = previousIds[link.arrowId];
    const start = toDayNumber(kept.schedule.dates[previousId].start) + link.days;
    if (start - toDayNumber(computed.schedule.dates[previousId].start) > mostDays) return computed;
    const { plan } = getTaskMove(kept.plan, previousId, toDay(start), kept.schedule);
    kept = { plan, schedule: computeSchedule(plan.tasks, plan.arrows) };
  }
  return kept;
}
