/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTimelineChanges, TTimelineDependency, TTimelineDependencyTypes, TTimelineIssue } from "@plane/types";
import { computeSchedule } from "./compute-schedule";
import { toDayNumber } from "./days";
import type { TArrowKind, TPlan, TScheduleArrow } from "./types";

/** What the plan needs of a stored work item. */
export type TStoredTask = Pick<TTimelineIssue, "id" | "start_date" | "target_date" | "is_start_fixed">;

const KINDS: [TTimelineDependencyTypes, TArrowKind][] = [
  ["blocking", "end-start"],
  ["start_before", "start-start"],
  ["finish_before", "end-end"],
];
const KIND_BY_RELATION_TYPE = Object.fromEntries(KINDS) as Record<TTimelineDependencyTypes, TArrowKind>;
const RELATION_TYPE_BY_KIND = Object.fromEntries(KINDS.map(([relationType, kind]) => [kind, relationType])) as Record<
  TArrowKind,
  TTimelineDependencyTypes
>;

const toArrow = (dependency: TTimelineDependency): TScheduleArrow => ({
  id: dependency.id,
  previousId: dependency.predecessor_id,
  nextId: dependency.dependent_id,
  kind: KIND_BY_RELATION_TYPE[dependency.relation_type],
  delay: dependency.delay ?? "linked",
});

/**
 * The plan of stored work items and dependencies. A work item without both dates, or with a start after its due
 * date, is not on the timeline, and its arrows take no part. A work item stored as following its arrows, to which
 * no arrow leads from a task of the timeline, stands fixed in the plan on its stored start.
 */
export function getPlan(issues: TStoredTask[], dependencies: TTimelineDependency[]): TPlan {
  const arrows = dependencies.map(toArrow);
  const onTimeline = issues.flatMap(({ id, start_date, target_date, is_start_fixed }) =>
    start_date && target_date && start_date <= target_date ? [{ id, start_date, target_date, is_start_fixed }] : []
  );
  const taskIds = new Set(onTimeline.map((issue) => issue.id));
  const followingIds = new Set(arrows.filter((arrow) => taskIds.has(arrow.previousId)).map((arrow) => arrow.nextId));
  return {
    tasks: onTimeline.map(({ id, start_date, target_date, is_start_fixed }) => ({
      id,
      duration: toDayNumber(target_date) - toDayNumber(start_date) + 1,
      start: is_start_fixed || !followingIds.has(id) ? { at: start_date } : "anchor",
    })),
    arrows,
  };
}

/**
 * What one request has to save of a plan: the arrows that differ from the stored dependencies, the tasks whose
 * computed dates differ from the stored ones or whose start an operation changed, and the tasks that were taken
 * off the timeline, which lose their dates and are fixed again, as a work item is that was never there.
 *
 * Whether a start is fixed is saved only when an operation changed that start: a plan says so by starting the
 * task otherwise than the plan of what is stored does. The stored field alone does not count. A work item stored
 * as following its arrows, to which no arrow leads, stands where it is and nothing is saved for it; somebody may
 * be replacing its arrow elsewhere in two steps, and it has to follow the new one.
 *
 * An arrow of another kind than its stored dependency is saved by removing the dependency and giving the new one.
 */
export function getChanges(issues: TStoredTask[], dependencies: TTimelineDependency[], plan: TPlan): TTimelineChanges {
  const { dates } = computeSchedule(plan.tasks, plan.arrows);
  const storedTasks = new Map(issues.map((issue) => [issue.id, issue]));
  const storedPlan = getPlan(issues, dependencies);
  const followingAsStored = new Set(storedPlan.tasks.flatMap((task) => (task.start === "anchor" ? [task.id] : [])));
  const idsInPlan = new Set(plan.tasks.map((task) => task.id));
  const storedArrows = new Map(dependencies.map((dependency) => [dependency.id, toArrow(dependency)]));
  const kindInPlan = new Map(plan.arrows.map((arrow) => [arrow.id, arrow.kind]));
  return {
    dependencies: plan.arrows
      .filter((arrow) => {
        const stored = storedArrows.get(arrow.id);
        return stored?.kind !== arrow.kind || stored.delay !== arrow.delay;
      })
      .map((arrow) => ({
        predecessor_id: arrow.previousId,
        dependent_id: arrow.nextId,
        relation_type: RELATION_TYPE_BY_KIND[arrow.kind],
        delay: arrow.delay === "linked" ? null : arrow.delay,
      })),
    removed_dependencies: [...storedArrows.values()]
      .filter((stored) => kindInPlan.get(stored.id) !== stored.kind)
      .map((stored) => stored.id),
    issues: [
      ...plan.tasks.flatMap((task) => {
        const stored = storedTasks.get(task.id);
        const { start, end } = dates[task.id];
        const isStartFixed = task.start !== "anchor";
        const isStartChanged = followingAsStored.has(task.id) === isStartFixed;
        return stored?.start_date === start && stored.target_date === end && !isStartChanged
          ? []
          : [{ id: task.id, start_date: start, target_date: end, is_start_fixed: isStartFixed }];
      }),
      ...storedPlan.tasks
        .filter((task) => !idsInPlan.has(task.id))
        .map((task) => ({ id: task.id, start_date: null, target_date: null, is_start_fixed: true })),
    ],
  };
}
