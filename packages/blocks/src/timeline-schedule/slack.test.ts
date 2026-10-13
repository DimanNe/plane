/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { computeSchedule } from "./compute-schedule";
import { toDay, toDayNumber } from "./days";
import { resizeTask } from "./gestures";
import { keepLinksTogether } from "./keep-links-together";
import { arrow, fixed, following } from "./test-helpers";
import { CHAIN_PLAN, getPlan, LINKED_ON, LINKED_ROUND, MIXED_PLAN, PLAN } from "./test-plans";
import type { TPlan, TSchedule } from "./types";

/** The days by which each arrow is not kept: its fixed next task is that much too early, or its link that far apart. */
const getDaysNotKept = ({ conflicts, apartLinks }: TSchedule): Record<string, number> => ({
  ...Object.fromEntries(
    conflicts.map(({ arrowId, askedDay, fixedDay }) => [arrowId, toDayNumber(askedDay) - toDayNumber(fixedDay)])
  ),
  ...Object.fromEntries(apartLinks.map(({ arrowId, days }) => [arrowId, days])),
});

/**
 * Whether the end of a task that is dragged later by some days gets there with nothing else changed: the task
 * starts where it did, every other task stands where it did, and no arrow is kept less than it was.
 */
const isEndMovedAlone = (plan: TPlan, taskId: string, days: number): boolean => {
  const before = computeSchedule(plan.tasks, plan.arrows);
  const end = toDay(toDayNumber(before.dates[taskId].end) + days);
  const after = keepLinksTogether(plan, resizeTask(plan, taskId, "end", end)).schedule;
  const daysNotKeptBefore = getDaysNotKept(before);
  return (
    plan.tasks.every(({ id }) => {
      const expected = id === taskId ? { start: before.dates[id].start, end } : before.dates[id];
      return after.dates[id].start === expected.start && after.dates[id].end === expected.end;
    }) &&
    Object.entries(getDaysNotKept(after)).every(
      ([arrowId, daysNotKept]) => daysNotKept <= (daysNotKeptBefore[arrowId] ?? 0)
    )
  );
};

describe("the slack of a task", () => {
  type TCase = { name: string; plan: TPlan; expected: TSchedule["slack"] };
  const cases: TCase[] = [
    {
      name: "an arrow out of the end gives the days its next task stands later than it asks, and none when it decides where the task stands",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 6), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 1), arrow("X>B", "end-start", 2)],
      },
      expected: { A: 4, X: 0 },
    },
    {
      name: "of several arrows out of the end the one that gives the fewest days counts",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("B", 10, 2), fixed("C", 7, 2)],
        arrows: [arrow("A>B", "end-start"), arrow("A>C", "end-end", 1)],
      },
      expected: { A: 4 },
    },
    {
      name: "an arrow into a fixed task is a check: the end before it can go later until the arrow would be a conflict",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 8, 2)], arrows: [arrow("A>B", "end-start", 1)] },
      expected: { A: 3 },
    },
    {
      name: "a check that is a conflict already gives no day",
      plan: { tasks: [fixed("A", 1, 5), fixed("B", 3, 2)], arrows: [arrow("A>B", "end-start")] },
      expected: { A: 0 },
    },
    {
      name: "a link into the end of a task that follows its arrows holds that end: the task it leads from would go along",
      plan: { tasks: [fixed("A", 1, 5), following("B", 3)], arrows: [arrow("A>B", "end-end", "linked")] },
      expected: { A: 0, B: 0 },
    },
    {
      name: "an in n d into the end of a task holds nothing: its n grows with the end",
      plan: { tasks: [fixed("A", 1, 5), following("B", 3)], arrows: [arrow("A>B", "end-end", 2)] },
      expected: { A: 0 },
    },
    {
      name: "a link that is apart gives the end it leads from the days it is apart, and holds the end it leads to",
      plan: {
        tasks: [fixed("A", 1, 4), fixed("X", 1, 3), following("B", 2)],
        arrows: [arrow("A>B", "end-end", "linked"), arrow("X>B", "end-start", 3)],
      },
      expected: { A: 4, X: 0, B: 0 },
    },
    {
      name: "a task whose end no arrow leads from and no link holds has none: an arrow out of its start does not limit its end",
      plan: {
        tasks: [fixed("A", 1, 3), following("B", 2), following("C", 2)],
        arrows: [arrow("A>B", "start-start", 1), arrow("B>C", "start-start", "linked")],
      },
      expected: {},
    },
    {
      name: "the owner's plan: only the task before the link has days, the two its in 14 d has of room",
      plan: CHAIN_PLAN,
      expected: {
        "chain 1": 0,
        "chain 2": 0,
        "chain 3": 0,
        "chain 4": 0,
        "chain 5": 0,
        "chain 6": 2,
        "chain 7": 0,
        "side 1": 0,
        "side 2": 0,
      },
    },
  ];

  it.each(cases)("$name", ({ plan, expected }) => {
    const actual = computeSchedule(plan.tasks, plan.arrows).slack;

    expect(actual).toEqual(expected);
  });

  it("is what a drag of the end does: by the slack the end moves alone, by a day more it does not, and without slack it moves alone however far", () => {
    const plans = [
      ...cases.map(({ name, plan }) => ({ name, plan })),
      { name: "the owner's plan in small", plan: PLAN },
      {
        name: "the owner's plan in small, linked on",
        plan: getPlan({ E: following("E", 2), F: fixed("F", 15, 6) }, LINKED_ON),
      },
      { name: "a round of links", plan: LINKED_ROUND },
      { name: "a plan with links, checks and a conflict", plan: MIXED_PLAN },
    ];

    const actual = plans.flatMap(({ name, plan }) => {
      const { slack } = computeSchedule(plan.tasks, plan.arrows);
      return plan.tasks.flatMap(({ id }) => {
        const days = slack[id];
        const isAsDragged =
          days === undefined
            ? [1, 30, 400].every((later) => isEndMovedAlone(plan, id, later))
            : isEndMovedAlone(plan, id, days) && !isEndMovedAlone(plan, id, days + 1);
        return isAsDragged ? [] : [`${name}: ${id}, slack ${days}`];
      });
    });

    expect(actual).toEqual([]);
  });
});
