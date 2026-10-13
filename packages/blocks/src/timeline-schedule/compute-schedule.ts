/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { toDay, toDayNumber } from "./days";
import type { TApartLink, TArrowDelay, TConflict, TSchedule, TScheduleArrow, TScheduleTask } from "./types";

/** The days an arrow asks for: a linked arrow asks for the same day as "in 0 d". */
export const getDelayDays = (delay: TArrowDelay): number => (delay === "linked" ? 0 : delay);

/** An arrow between two tasks of the timeline: their places in `tasks`, and the start it asks of the next one. */
type TLink = { arrow: TScheduleArrow; previous: number; next: number; askedStart: number };

/**
 * Computes the plan from its parameters: where every task stands, which arrows a fixed task contradicts, how far
 * the end of each task can go later and which tasks and arrows are critical. The scheduling rules of the timeline
 * are here and nowhere else.
 *
 * An arrow takes part only when both its tasks are among `tasks`: a work item without dates is not on the
 * timeline. Throws when the arrows form a loop, and when a task follows its arrows but none leads to it; the
 * functions that build or change a plan produce neither.
 */
export function computeSchedule(tasks: TScheduleTask[], arrows: TScheduleArrow[]): TSchedule {
  const indexById = new Map(tasks.map((task, index) => [task.id, index]));
  const links: TLink[] = [];
  const incoming: TLink[][] = tasks.map(() => []);
  const outgoing: TLink[][] = tasks.map(() => []);
  for (const arrow of arrows) {
    const previous = indexById.get(arrow.previousId);
    const next = indexById.get(arrow.nextId);
    if (previous === undefined || next === undefined) continue;
    const link = { arrow, previous, next, askedStart: 0 };
    links.push(link);
    incoming[next].push(link);
    outgoing[previous].push(link);
  }

  // every task after the previous tasks of its arrows
  const unplacedBefore = incoming.map((into) => into.length);
  const order = tasks.flatMap((_task, index) => (unplacedBefore[index] === 0 ? [index] : []));
  for (let position = 0; position < order.length; position++)
    for (const { next } of outgoing[order[position]]) {
      unplacedBefore[next] -= 1;
      if (unplacedBefore[next] === 0) order.push(next);
    }
  if (order.length < tasks.length) {
    const unplaced = tasks.filter((_task, index) => unplacedBefore[index] > 0).map((task) => task.id);
    throw new Error(`The arrows form a loop, so these tasks cannot be placed: ${unplaced.join(", ")}`);
  }

  const start = tasks.map(() => 0);
  const decidingArrowId: TSchedule["decidingArrowId"] = {};
  for (const index of order) {
    const task = tasks[index];
    let deciding: TLink | undefined;
    for (const link of incoming[index]) {
      const { kind, delay } = link.arrow;
      const anchor = start[link.previous] + (kind === "start-start" ? 0 : tasks[link.previous].duration - 1);
      // end -> start asks for the day after the anchor, so that with no days between them the bars touch;
      // end -> end asks for the end, and the start follows from the duration
      link.askedStart =
        anchor + getDelayDays(delay) + (kind === "end-start" ? 1 : kind === "end-end" ? 1 - task.duration : 0);
      if (!deciding || link.askedStart > deciding.askedStart) deciding = link;
    }
    if (task.start !== "anchor") start[index] = toDayNumber(task.start.at);
    else if (deciding) {
      start[index] = deciding.askedStart;
      decidingArrowId[task.id] = deciding.arrow.id;
    } else throw new Error(`Task ${task.id} follows its arrows, but no arrow leads to it`);
  }

  const dates: TSchedule["dates"] = {};
  tasks.forEach((task, index) => {
    dates[task.id] = { start: toDay(start[index]), end: toDay(start[index] + task.duration - 1) };
  });

  const gaps: TSchedule["gaps"] = {};
  const conflicts: TConflict[] = [];
  const apartLinks: TApartLink[] = [];
  const slack: TSchedule["slack"] = {};
  const limitSlack = (index: number, days: number) => {
    const { id } = tasks[index];
    slack[id] = Math.min(slack[id] ?? Infinity, days);
  };
  for (const { arrow, previous, next, askedStart } of links) {
    const gap = getDelayDays(arrow.delay) + start[next] - askedStart;
    gaps[arrow.id] = gap;
    const task = tasks[next];
    // The end an arrow leads from can go later by the days the next task stands later than the arrow asks. A day
    // more pushes that task; fixed on its day, the task is then too early for the arrow, and gives no day when it
    // is so already.
    if (arrow.kind !== "start-start") limitSlack(previous, Math.max(start[next] - askedStart, 0));
    // A link holds the end it leads to as well: that end takes the previous task along, or, the link being apart,
    // goes further from it.
    if (arrow.kind === "end-end" && arrow.delay === "linked" && task.start === "anchor") limitSlack(next, 0);
    const heldByArrowId = decidingArrowId[task.id];
    if (arrow.delay === "linked" && heldByArrowId && askedStart < start[next])
      apartLinks.push({ arrowId: arrow.id, taskId: task.id, days: gap, heldByArrowId });
    if (task.start === "anchor" || askedStart <= start[next]) continue;
    const askedDay = toDay(askedStart);
    conflicts.push({
      arrowId: arrow.id,
      taskId: task.id,
      fixedDay: task.start.at,
      askedDay,
      anchorDay: dates[arrow.previousId][arrow.kind === "start-start" ? "start" : "end"],
      waysOut: [
        { way: "follow-arrows" },
        { way: "move-fixed-day", day: askedDay },
        ...(gap >= 0 ? [{ way: "shorten-delay" as const, delay: gap }] : []),
        { way: "remove-arrow" },
      ],
    });
  }

  // groups of tasks connected by arrows in either direction: their size and their last end
  const groupOf = tasks.map(() => -1);
  const groups: { size: number; lastEnd: number }[] = [];
  tasks.forEach((_task, first) => {
    if (groupOf[first] !== -1) return;
    const members: number[] = [];
    const group = { size: 0, lastEnd: -Infinity };
    const join = (index: number) => {
      if (groupOf[index] !== -1) return;
      groupOf[index] = groups.length;
      members.push(index);
      group.lastEnd = Math.max(group.lastEnd, start[index] + tasks[index].duration - 1);
    };
    join(first);
    for (let position = 0; position < members.length; position++) {
      for (const { previous } of incoming[members[position]]) join(previous);
      for (const { next } of outgoing[members[position]]) join(next);
    }
    group.size = members.length;
    groups.push(group);
  });

  // backward from the last end of each group: the latest start of every task that keeps it
  const isCritical = tasks.map(() => false);
  const latestStart = tasks.map(() => 0);
  for (let position = order.length - 1; position >= 0; position--) {
    const index = order[position];
    const group = groups[groupOf[index]];
    if (group.size <= 2) continue;
    let latest = group.lastEnd - tasks[index].duration + 1;
    for (const { next, askedStart } of outgoing[index]) {
      // A next task that follows its arrows moves along, as late as it may start itself. A fixed one stays: this
      // task can slip until the arrow would become a conflict, and not at all when it is one already.
      const limit = tasks[next].start === "anchor" ? latestStart[next] : Math.max(start[next], askedStart);
      latest = Math.min(latest, start[index] + limit - askedStart);
    }
    latestStart[index] = latest;
    isCritical[index] = latest === start[index];
  }

  return {
    dates,
    decidingArrowId,
    gaps,
    conflicts,
    apartLinks,
    slack,
    criticalTaskIds: tasks.filter((_task, index) => isCritical[index]).map((task) => task.id),
    criticalArrowIds: links
      .filter(
        ({ previous, next, askedStart }) => isCritical[previous] && isCritical[next] && askedStart === start[next]
      )
      .map(({ arrow }) => arrow.id),
  };
}

/**
 * The tasks and arrows that produce a conflict, for highlighting: the fixed task, the conflicting arrow and its
 * previous task, and from there back along the arrows that decide each start, to a fixed task.
 */
export function getConflictCause(
  arrows: TScheduleArrow[],
  schedule: TSchedule,
  conflict: TConflict
): { taskIds: string[]; arrowIds: string[] } {
  const previousIdByArrowId = new Map(arrows.map((arrow) => [arrow.id, arrow.previousId]));
  const taskIds = [conflict.taskId];
  const arrowIds: string[] = [];
  for (let arrowId: string | undefined = conflict.arrowId; arrowId; ) {
    const previousId = previousIdByArrowId.get(arrowId);
    if (previousId === undefined) break;
    arrowIds.push(arrowId);
    taskIds.push(previousId);
    arrowId = schedule.decidingArrowId[previousId];
  }
  return { taskIds, arrowIds };
}
