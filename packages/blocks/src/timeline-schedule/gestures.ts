/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { computeSchedule } from "./compute-schedule";
import { toDay, toDayNumber } from "./days";
import type {
  TArrowKind,
  TConflict,
  TDay,
  TPlan,
  TRefusal,
  TScheduleArrow,
  TScheduleTask,
  TTaskEdge,
  TTaskStart,
  TWayOut,
} from "./types";

// Each function turns a gesture into changed parameters and returns a new plan; the plan it was given stays as it
// was. A preview is the schedule of the returned plan, and dropping the returned plan aborts the gesture.

const getTask = (plan: TPlan, taskId: string): TScheduleTask => {
  const task = plan.tasks.find((candidate) => candidate.id === taskId);
  if (!task) throw new Error(`Task ${taskId} is not on the timeline`);
  return task;
};

const getArrow = (plan: TPlan, arrowId: string): TScheduleArrow => {
  const arrow = plan.arrows.find((candidate) => candidate.id === arrowId);
  if (!arrow) throw new Error(`Arrow ${arrowId} is not on the timeline`);
  return arrow;
};

const setStart = (plan: TPlan, taskId: string, start: TTaskStart): TPlan => ({
  tasks: plan.tasks.map((task) => (task.id === taskId ? { ...task, start } : task)),
  arrows: plan.arrows,
});

/** The edge of its next task that an arrow constrains. */
const getConstrainedEdge = (kind: TArrowKind): TTaskEdge => (kind === "end-end" ? "end" : "start");

/** The kind of an arrow drawn from an edge of one bar to an edge of another; start to end does not exist. */
export function getArrowKind(previousEdge: TTaskEdge, nextEdge: TTaskEdge): TArrowKind | undefined {
  const kind = `${previousEdge}-${nextEdge}` as const;
  return kind === "start-end" ? undefined : kind;
}

/**
 * Moves the given edges of a task to the day. Of a fixed task the day or the duration changes. A task that
 * follows its arrows stands where they ask, so the delay of its deciding arrow changes when that arrow constrains
 * a moved edge. A moved edge goes no earlier than its other arrows ask for, nor before "immediately" on the
 * deciding arrow; the other arrows keep their delay. One edge alone stops where the task is one day long.
 */
function moveEdges(plan: TPlan, taskId: string, edges: TTaskEdge[], day: TDay): TPlan {
  const task = getTask(plan, taskId);
  const schedule = computeSchedule(plan.tasks, plan.arrows);
  const decidingArrowId = schedule.decidingArrowId[taskId];
  const moves = (edge: TTaskEdge) => edges.includes(edge);
  let earliest = moves("start") ? -Infinity : 1 - task.duration;
  const latest = moves("end") ? Infinity : task.duration - 1;
  if (task.start === "anchor")
    for (const arrow of plan.arrows) {
      if (arrow.nextId !== taskId || !(arrow.id in schedule.gaps) || !moves(getConstrainedEdge(arrow.kind))) continue;
      const room = arrow.id === decidingArrowId ? arrow.delay : schedule.gaps[arrow.id] - arrow.delay;
      earliest = Math.max(earliest, -room);
    }
  const wanted = toDayNumber(day) - toDayNumber(schedule.dates[taskId][edges[0]]);
  const days = Math.min(latest, Math.max(earliest, wanted));
  return {
    tasks: plan.tasks.map((other) =>
      other === task
        ? {
            ...task,
            duration: task.duration + (moves("end") ? days : 0) - (moves("start") ? days : 0),
            start:
              task.start !== "anchor" && moves("start") ? { at: toDay(toDayNumber(task.start.at) + days) } : task.start,
          }
        : other
    ),
    arrows: plan.arrows.map((arrow) =>
      arrow.id === decidingArrowId && moves(getConstrainedEdge(arrow.kind))
        ? { ...arrow, delay: arrow.delay + days }
        : arrow
    ),
  };
}

/** A bar dragged horizontally: the task starts on the day and keeps its duration. */
export const moveTask = (plan: TPlan, taskId: string, day: TDay): TPlan =>
  moveEdges(plan, taskId, ["start", "end"], day);

/** An edge of a bar dragged: that edge goes to the day and the other edge stays. */
export const resizeTask = (plan: TPlan, taskId: string, edge: TTaskEdge, day: TDay): TPlan =>
  moveEdges(plan, taskId, [edge], day);

/** A task put on the timeline: it is fixed on the day, one day long unless it has a duration already. */
export function placeTask(plan: TPlan, taskId: string, day: TDay): TPlan {
  if (plan.tasks.some((task) => task.id === taskId)) return setStart(plan, taskId, { at: day });
  return { tasks: [...plan.tasks, { id: taskId, duration: 1, start: { at: day } }], arrows: plan.arrows };
}

const leadsTo = (arrows: TScheduleArrow[], fromId: string, toId: string): boolean => {
  const reached = [fromId];
  const seen = new Set(reached);
  for (let position = 0; position < reached.length; position++)
    for (const arrow of arrows) {
      if (arrow.previousId !== reached[position] || seen.has(arrow.nextId)) continue;
      seen.add(arrow.nextId);
      reached.push(arrow.nextId);
    }
  return seen.has(toId);
};

/**
 * An arrow drawn between two bars: it asks "immediately", and its next task follows its arrows from now on.
 * Refused between a task and itself, between tasks that have an arrow in this direction, and when it would close
 * a loop. The new arrow's id lasts until the plan is saved; the server gives it another.
 */
export function addArrow(plan: TPlan, previousId: string, nextId: string, kind: TArrowKind): TPlan | TRefusal {
  if (previousId === nextId) return { refused: "same-task" };
  if (plan.arrows.some((arrow) => arrow.previousId === previousId && arrow.nextId === nextId))
    return { refused: "already-connected" };
  if (leadsTo(plan.arrows, nextId, previousId)) return { refused: "loop" };
  return {
    tasks: setStart(plan, nextId, "anchor").tasks,
    arrows: [...plan.arrows, { id: `${previousId}:${nextId}`, previousId, nextId, kind, delay: 0 }],
  };
}

/**
 * A new kind (an end of the arrow dragged to the other edge of the same bar) or a new delay ("immediately" is 0).
 * Setting a delay makes the next task follow its arrows.
 */
export function changeArrow(plan: TPlan, arrowId: string, change: { kind?: TArrowKind; delay?: number }): TPlan {
  const arrow = getArrow(plan, arrowId);
  return {
    tasks: change.delay === undefined ? plan.tasks : setStart(plan, arrow.nextId, "anchor").tasks,
    arrows: plan.arrows.map((other) =>
      other === arrow ? { ...arrow, kind: change.kind ?? arrow.kind, delay: change.delay ?? arrow.delay } : other
    ),
  };
}

/** A task that followed its arrows and has none left from a task of the timeline is fixed on the day it stood on. */
export function removeArrow(plan: TPlan, arrowId: string): TPlan {
  const arrow = getArrow(plan, arrowId);
  const arrows = plan.arrows.filter((other) => other !== arrow);
  const next = plan.tasks.find((task) => task.id === arrow.nextId);
  const isFollowed = arrows.some(
    (other) => other.nextId === arrow.nextId && plan.tasks.some((task) => task.id === other.previousId)
  );
  if (next?.start !== "anchor" || isFollowed) return { tasks: plan.tasks, arrows };
  const day = computeSchedule(plan.tasks, plan.arrows).dates[next.id].start;
  return { tasks: setStart(plan, next.id, { at: day }).tasks, arrows };
}

/**
 * "on [date]" in the control of an arrow: the next task is fixed so that the edge the arrow constrains is on the
 * day, its start, or its end for an end -> end arrow. Its arrows become checks.
 */
export function fixNextTask(plan: TPlan, arrowId: string, day: TDay): TPlan {
  const arrow = getArrow(plan, arrowId);
  const daysBeforeEdge = arrow.kind === "end-end" ? getTask(plan, arrow.nextId).duration - 1 : 0;
  return setStart(plan, arrow.nextId, { at: toDay(toDayNumber(day) - daysBeforeEdge) });
}

export function applyWayOut(plan: TPlan, conflict: TConflict, wayOut: TWayOut): TPlan {
  switch (wayOut.way) {
    case "follow-arrows":
      return setStart(plan, conflict.taskId, "anchor");
    case "move-fixed-day":
      return setStart(plan, conflict.taskId, { at: wayOut.day });
    case "shorten-delay":
      return {
        tasks: plan.tasks,
        arrows: plan.arrows.map((arrow) => (arrow.id === conflict.arrowId ? { ...arrow, delay: wayOut.delay } : arrow)),
      };
    case "remove-arrow":
      return removeArrow(plan, conflict.arrowId);
  }
}
