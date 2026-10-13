/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { arrow, fixed, following } from "./test-helpers";
import type { TDay, TPlan, TScheduleArrow, TScheduleTask } from "./types";

// The plans that the tests of more than one rule are tried on.

/**
 * The plan of the owner's test project, under other names. A chain of in n d leads from chain 1 to chain 7, which
 * stands 2 days later than its in 14 d asks: side 1, fixed on its day, is linked to its end, and two more tasks
 * are linked on.
 */
export const getChainPlan = (sideStart: TDay, delays: Record<string, number>): TPlan => ({
  tasks: [
    { id: "chain 1", duration: 61, start: { at: "2026-11-01" } },
    following("chain 2", 12),
    following("chain 3", 28),
    following("chain 4", 29),
    following("chain 5", 12),
    following("chain 6", 13),
    following("chain 7", 12),
    { id: "side 1", duration: 24, start: { at: sideStart } },
    following("side 2", 13),
    following("side 3", 29),
  ],
  arrows: [
    arrow("chain 1>chain 2", "end-start", 40),
    arrow("chain 2>chain 3", "end-start", 7),
    arrow("chain 3>chain 4", "end-start", 35),
    arrow("chain 4>chain 5", "end-start", delays["chain 4>chain 5"] ?? 36),
    arrow("chain 5>chain 6", "end-start", delays["chain 5>chain 6"] ?? 36),
    arrow("chain 6>chain 7", "end-start", delays["chain 6>chain 7"] ?? 14),
    arrow("side 1>chain 7", "end-end", "linked"),
    arrow("side 1>side 2", "end-start", "linked"),
    arrow("side 2>side 3", "end-start", "linked"),
  ],
});
// chain 6 stands from 2027-08-24, chain 5 from 2027-07-07
export const CHAIN_PLAN = getChainPlan("2027-09-10", {});

// The owner's plan in small. X ends on the 3rd and asks B to start in 3 d, on the 7th. A is fixed from the 8th to
// the 13th and B is linked to its end, so B stands from the 10th, 3 days later than the in n d asks. C stands from
// the 14th and D from the 17th, linked on.
const TASKS = {
  X: fixed("X", 1, 3),
  A: fixed("A", 8, 6),
  B: following("B", 4),
  C: following("C", 3),
  D: following("D", 2),
};
export const ARROWS = {
  XB: arrow("X>B", "end-start", 3),
  AB: arrow("A>B", "end-end", "linked"),
  AC: arrow("A>C", "end-start", "linked"),
  CD: arrow("C>D", "end-start", "linked"),
};
/** That plan with other tasks and arrows in the place of those of the same name, and with more of them at its end. */
export const getPlan = (tasks: Record<string, TScheduleTask>, arrows: Record<string, TScheduleArrow> = {}): TPlan => ({
  tasks: Object.values({ ...TASKS, ...tasks }),
  arrows: Object.values({ ...ARROWS, ...arrows }),
});
export const PLAN = getPlan({});

// D asks E to start in 0 d, on the 19th, and F, fixed from the 15th to the 20th, is linked to the end of E: no room
export const LINKED_ON = { DE: arrow("D>E", "end-start", 0), FE: arrow("F>E", "end-end", "linked") };

// a chain of links whose last task has its other edge joined to the first one: all three are together
export const LINKED_ROUND: TPlan = {
  tasks: [fixed("P", 1, 3), following("M", 6), following("N", 3)],
  arrows: [
    arrow("P>N", "end-start", "linked"),
    arrow("P>M", "start-start", "linked"),
    arrow("M>N", "end-end", "linked"),
  ],
};

// W leads to X and X to B through in n d, with a day of room. A is fixed and linked to the end of B, C and D are
// linked on, D pushes E, and F is fixed and linked to the end of E. Z is fixed a day before K asks, a conflict,
// and asks B for the day it stands on. S and L stand apart, before and after all of these.
export const MIXED_PLAN: TPlan = {
  tasks: [
    fixed("W", 1, 2),
    following("X", 3),
    fixed("A", 9, 6),
    following("B", 4),
    following("C", 3),
    following("D", 2),
    following("E", 2),
    fixed("F", 16, 6),
    fixed("K", 1, 2),
    fixed("Z", 2, 2),
    fixed("S", 1, 1),
    fixed("L", 26, 2),
  ],
  arrows: [
    arrow("W>X", "end-start", 1),
    arrow("X>B", "end-start", 3),
    arrow("A>B", "end-end", "linked"),
    arrow("A>C", "end-start", "linked"),
    arrow("C>D", "end-start", "linked"),
    arrow("D>E", "end-start", 0),
    arrow("F>E", "end-end", "linked"),
    arrow("K>Z", "end-start", 0),
    arrow("Z>B", "end-start", 7),
  ],
};
