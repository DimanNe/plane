/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { getChangedArrowIds } from "./changed-arrows";
import { computeSchedule } from "./compute-schedule";
import { addArrow, moveTask, resizeTask, setArrowMode } from "./gestures";
import { keepLinksTogether } from "./keep-links-together";
import { arrow, day, fixed } from "./test-helpers";
import { CHAIN_PLAN, PLAN } from "./test-plans";
import type { TPlan } from "./types";

describe("getChangedArrowIds", () => {
  type TCase = { name: string; before: TPlan; operate: (plan: TPlan) => TPlan; expected: string[] };
  const cases: TCase[] = [
    {
      name: "the owner's plan: the arrows of a chain that is pushed keep their length, and the arrow whose room the push takes gets shorter",
      before: CHAIN_PLAN,
      operate: (plan) => resizeTask(plan, "chain 1", "end", "2027-01-01"),
      expected: ["chain 6>chain 7"],
    },
    {
      name: "the owner's plan: that arrow stays shorter than it was when its room is used up and its next task is pushed too",
      before: CHAIN_PLAN,
      operate: (plan) => resizeTask(plan, "chain 1", "end", "2027-01-05"),
      expected: ["chain 6>chain 7"],
    },
    {
      name: "the owner's plan: a task moved later changes the n of the arrow it follows and the length of the arrow before the task that stays",
      before: CHAIN_PLAN,
      operate: (plan) => moveTask(plan, "chain 6", "2027-08-26"),
      expected: ["chain 5>chain 6", "chain 6>chain 7"],
    },
    {
      name: "an arrow into a fixed task is as long as the days between its edges, which a move of the task changes",
      before: { tasks: [fixed("A", 1, 3), fixed("B", 8, 2)], arrows: [arrow("A>B", "end-start", 1)] },
      operate: (plan) => moveTask(plan, "B", day(10)),
      expected: ["A>B"],
    },
    {
      name: "an arrow turned from linked to in 0 d asks for something else, though nothing moves",
      before: PLAN,
      operate: (plan) => setArrowMode(plan, "C>D", "in"),
      expected: ["C>D"],
    },
    {
      name: "a new arrow is changed, and the arrows around it are not when nothing moves",
      before: PLAN,
      operate: (plan) => addArrow(plan, "X", "D", "end-start") as TPlan,
      expected: ["X:D"],
    },
  ];

  it.each(cases)("$name", ({ before, operate, expected }) => {
    const schedule = computeSchedule(before.tasks, before.arrows);

    const actual = getChangedArrowIds({ plan: before, schedule }, keepLinksTogether(before, operate(before)));

    expect(actual).toEqual(expected);
  });
});
