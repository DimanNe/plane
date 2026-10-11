/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { computeSchedule, getDelayDays } from "./compute-schedule";
import { toDay, toDayNumber } from "./days";
import type {
  TArrowDelay,
  TArrowKind,
  TArrowMode,
  TConflict,
  TDay,
  TPlan,
  TRefusal,
  TSchedule,
  TScheduleArrow,
  TScheduleTask,
  TTaskEdge,
  TTaskMove,
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

/** The edge of its previous task that an arrow leads from. */
const getPreviousEdge = (kind: TArrowKind): TTaskEdge => (kind === "start-start" ? "start" : "end");

/**
 * Moves the given edges of a task to the day, and with them the body of the task: every task that a link joins
 * to a moved edge, and every task that links join to those. A link keeps its two edges together whichever of its
 * tasks is moved, so the tasks of the body go along as a whole, by the same days. No move makes a link come
 * apart: where the body cannot go further, the moved edges stop.
 *
 * What takes up the move:
 * - a task of the body that is fixed on its day gets another day;
 * - an "in n d" that leads into the body from outside gives the days its task stands later than it asks, then
 *   its n, down to 0, where it stops the move; a link that is apart stops the move where its edges come together;
 * - a task that nothing holds on its later day has the n of its deciding arrow grow.
 * What follows the body from outside follows as the plan computes; where that pushes a task off a link from a
 * task that stayed, `keepLinksTogether` brings the two together. An arrow into a task that is fixed on its day
 * is a check, and stops nothing. One edge alone stops where its task is one day long.
 */
function getEdgesMove(
  plan: TPlan,
  taskId: string,
  edges: TTaskEdge[],
  day: TDay,
  schedule = computeSchedule(plan.tasks, plan.arrows)
): TTaskMove {
  const task = getTask(plan, taskId);
  const followingIds = new Set(plan.tasks.flatMap((other) => (other.start === "anchor" ? [other.id] : [])));
  const arrows = plan.arrows.flatMap((arrow) => {
    const gap = schedule.gaps[arrow.id];
    if (gap === undefined) return [];
    return [{ arrow, gap, previousEdge: getPreviousEdge(arrow.kind), nextEdge: getConstrainedEdge(arrow.kind) }];
  });

  // the tasks that go along as a whole; of the moved task itself the given edges move
  const bodyIds = new Set<string>();
  const isMoved = (id: string, edge: TTaskEdge) => (id === taskId ? edges.includes(edge) : bodyIds.has(id));
  // an edge of the moved task that stays is joined to the body: the body cannot move
  let isHeldByOwnEdge = false;
  const links = arrows.filter(
    ({ arrow, gap }) => arrow.delay === "linked" && gap === 0 && followingIds.has(arrow.nextId)
  );
  const joinTasksLinkedTo = (id: string) => {
    for (const { arrow, previousEdge, nextEdge } of links) {
      const [ownEdge, otherId, otherEdge] =
        arrow.nextId === id ? [nextEdge, arrow.previousId, previousEdge] : [previousEdge, arrow.nextId, nextEdge];
      if ((arrow.nextId !== id && arrow.previousId !== id) || !isMoved(id, ownEdge) || isMoved(otherId, otherEdge))
        continue;
      if (otherId === taskId) isHeldByOwnEdge = true;
      else {
        bodyIds.add(otherId);
        joinTasksLinkedTo(otherId);
      }
    }
  };
  joinTasksLinkedTo(taskId);

  // the arrows that lead into the body from outside: the edge they constrain moves, the edge they lead from stays
  const arrowsIntoBody = arrows.filter(
    ({ arrow, previousEdge, nextEdge }) =>
      followingIds.has(arrow.nextId) && isMoved(arrow.nextId, nextEdge) && !isMoved(arrow.previousId, previousEdge)
  );
  // an arrow lets its edge go as far earlier as there are days between its two edges
  const earliest = Math.max(
    edges.includes("start") ? -Infinity : 1 - task.duration,
    ...arrowsIntoBody.map(({ gap }) => -gap)
  );
  const latest = edges.includes("end") ? Infinity : task.duration - 1;
  const wanted = toDayNumber(day) - toDayNumber(schedule.dates[taskId][edges[0]]);
  const days = isHeldByOwnEdge ? 0 : Math.min(latest, Math.max(earliest, wanted));

  const delays = new Map<string, number>();
  for (const { arrow, gap } of arrowsIntoBody)
    if (arrow.delay !== "linked" && gap + days < arrow.delay) delays.set(arrow.id, gap + days);
  // A task that moves later stays there when an arrow that held it holds it still: one whose two edges move
  // together, or of the moved task one on the edge that stays. Else its deciding arrow has to ask for the later day.
  if (days > 0)
    for (const id of [taskId, ...bodyIds]) {
      if (!followingIds.has(id)) continue;
      const isHeld = arrows.some(
        ({ arrow, gap, previousEdge, nextEdge }) =>
          arrow.nextId === id &&
          gap === getDelayDays(arrow.delay) &&
          isMoved(id, nextEdge) === isMoved(arrow.previousId, previousEdge)
      );
      const deciding = plan.arrows.find((arrow) => arrow.id === schedule.decidingArrowId[id]);
      if (!isHeld && deciding && deciding.delay !== "linked") delays.set(deciding.id, deciding.delay + days);
    }

  const moveStart = (start: TTaskStart): TTaskStart =>
    start === "anchor" ? start : { at: toDay(toDayNumber(start.at) + days) };
  return {
    plan: {
      tasks: plan.tasks.map((other) => {
        if (other === task)
          return {
            ...task,
            duration: task.duration + (edges.includes("end") ? days : 0) - (edges.includes("start") ? days : 0),
            start: edges.includes("start") ? moveStart(task.start) : task.start,
          };
        return bodyIds.has(other.id) ? { ...other, start: moveStart(other.start) } : other;
      }),
      arrows: plan.arrows.map((arrow) =>
        delays.has(arrow.id) ? { ...arrow, delay: delays.get(arrow.id) ?? 0 } : arrow
      ),
    },
    stoppingArrowIds:
      days > wanted ? arrowsIntoBody.flatMap(({ arrow, gap }) => (gap + days === 0 ? [arrow.id] : [])) : [],
  };
}

/**
 * A bar dragged horizontally: the task starts on the day and keeps its duration. A caller that has computed the
 * schedule of the plan gives it, and it is not computed again.
 */
export const getTaskMove = (plan: TPlan, taskId: string, day: TDay, schedule?: TSchedule): TTaskMove =>
  getEdgesMove(plan, taskId, ["start", "end"], day, schedule);

/** An edge of a bar dragged: that edge goes to the day and the other edge stays. */
export const getTaskResize = (plan: TPlan, taskId: string, edge: TTaskEdge, day: TDay): TTaskMove =>
  getEdgesMove(plan, taskId, [edge], day);

/** The plan after a bar was dragged horizontally. */
export const moveTask = (plan: TPlan, taskId: string, day: TDay): TPlan => getTaskMove(plan, taskId, day).plan;

/** The plan after an edge of a bar was dragged. */
export const resizeTask = (plan: TPlan, taskId: string, edge: TTaskEdge, day: TDay): TPlan =>
  getTaskResize(plan, taskId, edge, day).plan;

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
 * An arrow drawn between two bars. It says what is there: "in n d" with the days between its two edges at this
 * moment, so that drawing it moves nothing; only a next task that stands before the edge moves, to "in 0 d". A
 * given delay is taken as it is. The next task follows its arrows from now on. Refused between a task and
 * itself, between tasks that have an arrow in this direction, and when it would close a loop. The new arrow's id
 * lasts until the plan is saved; the server gives it another.
 */
export function addArrow(
  plan: TPlan,
  previousId: string,
  nextId: string,
  kind: TArrowKind,
  delay?: TArrowDelay
): TPlan | TRefusal {
  if (previousId === nextId) return { refused: "same-task" };
  if (plan.arrows.some((arrow) => arrow.previousId === previousId && arrow.nextId === nextId))
    return { refused: "already-connected" };
  if (leadsTo(plan.arrows, nextId, previousId)) return { refused: "loop" };
  const arrow = { id: `${previousId}:${nextId}`, previousId, nextId, kind };
  // The gap of an arrow that asks "in 0 d" is the days there are. An arrow to or from a work item without dates
  // has none.
  const getDaysThere = () =>
    Math.max(computeSchedule(plan.tasks, [...plan.arrows, { ...arrow, delay: 0 }]).gaps[arrow.id] ?? 0, 0);
  return {
    tasks: setStart(plan, nextId, "anchor").tasks,
    arrows: [...plan.arrows, { ...arrow, delay: delay ?? getDaysThere() }],
  };
}

/**
 * A new kind (an end of the arrow dragged to the other edge of the same bar) or a new delay, "linked" or the n of
 * "in n d". Setting a delay makes the next task follow its arrows.
 */
export function changeArrow(plan: TPlan, arrowId: string, change: { kind?: TArrowKind; delay?: TArrowDelay }): TPlan {
  const arrow = getArrow(plan, arrowId);
  return {
    tasks: change.delay === undefined ? plan.tasks : setStart(plan, arrow.nextId, "anchor").tasks,
    arrows: plan.arrows.map((other) =>
      other === arrow ? { ...arrow, kind: change.kind ?? arrow.kind, delay: change.delay ?? arrow.delay } : other
    ),
  };
}

/** How an arrow holds its next task. */
export const getArrowMode = (plan: TPlan, arrow: TScheduleArrow): TArrowMode =>
  getTask(plan, arrow.nextId).start !== "anchor" ? "on" : arrow.delay === "linked" ? "linked" : "in";

/**
 * Sets how an arrow holds its next task, and moves as little as that allows. "linked" brings the two edges
 * together, which moves the task when it stood apart. "in" says the days there are between the edges, none for
 * a link whose edges were together, so that only a task that stood before the edge moves. "on" fixes the task on
 * the day it stands on; the arrow keeps what it asked.
 */
export function setArrowMode(plan: TPlan, arrowId: string, mode: TArrowMode): TPlan {
  const arrow = getArrow(plan, arrowId);
  const current = getArrowMode(plan, arrow);
  if (mode === current) return plan;
  if (mode === "linked") return changeArrow(plan, arrowId, { delay: "linked" });
  const schedule = computeSchedule(plan.tasks, plan.arrows);
  if (mode === "on") return setStart(plan, arrow.nextId, { at: schedule.dates[arrow.nextId].start });
  return changeArrow(plan, arrowId, { delay: Math.max(schedule.gaps[arrowId], 0) });
}

const MODES: TArrowMode[] = ["linked", "in", "on"];

/** The wheel on what an arrow is: a step round linked, in, on and linked again, or the other way. */
export function turnArrowMode(plan: TPlan, arrowId: string, direction: 1 | -1): TPlan {
  const index = MODES.indexOf(getArrowMode(plan, getArrow(plan, arrowId)));
  return setArrowMode(plan, arrowId, MODES[(index + direction + MODES.length) % MODES.length]);
}

/**
 * Of the arrows that lead to a task, the one that asks for the latest day. It decides where the task stands when
 * the task follows its arrows; of a task that is fixed on its day it is the one that would.
 */
export function getLatestArrowId(arrows: TScheduleArrow[], schedule: TSchedule, taskId: string): string | undefined {
  let latest: { id: string; room: number } | undefined;
  for (const arrow of arrows) {
    if (arrow.nextId !== taskId || !(arrow.id in schedule.gaps)) continue;
    const room = schedule.gaps[arrow.id] - getDelayDays(arrow.delay);
    if (!latest || room < latest.room) latest = { id: arrow.id, room };
  }
  return latest?.id;
}

/**
 * A task taken off the timeline: it has no dates any more, and its arrows are removed with it, those that lead to
 * it and those that lead from it. No other task moves: a task that followed one of those arrows and that no arrow
 * holds on its day any more is fixed on the day it stood on.
 */
export function removeTask(plan: TPlan, taskId: string): TPlan {
  const schedule = computeSchedule(plan.tasks, plan.arrows);
  const arrows = plan.arrows.filter((arrow) => arrow.previousId !== taskId && arrow.nextId !== taskId);
  // an arrow whose gap is the days it asks for asks for exactly the day its next task stands on
  const heldIds = new Set(
    arrows.flatMap((arrow) => (schedule.gaps[arrow.id] === getDelayDays(arrow.delay) ? [arrow.nextId] : []))
  );
  return {
    tasks: plan.tasks.flatMap((task) => {
      if (task.id === taskId) return [];
      if (task.start !== "anchor" || heldIds.has(task.id)) return [task];
      return [{ ...task, start: { at: schedule.dates[task.id].start } }];
    }),
    arrows,
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
