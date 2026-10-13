/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { computeSchedule } from "./compute-schedule";
import {
  addArrow,
  applyWayOut,
  changeArrow,
  fixNextTask,
  moveTask,
  placeTask,
  removeArrow,
  removeTask,
  resizeTask,
  setArrowMode,
  turnArrowMode,
} from "./gestures";
import { keepLinksTogether } from "./keep-links-together";
import { arrow, day, fixed, following } from "./test-helpers";
import { ARROWS, CHAIN_PLAN, getChainPlan, getPlan, LINKED_ON, LINKED_ROUND, MIXED_PLAN, PLAN } from "./test-plans";
import type { TArrowKind, TArrowMode, TPlan, TRefusal, TTaskEdge } from "./types";

describe("keepLinksTogether", () => {
  type TCase = { name: string; before: TPlan; operate: (plan: TPlan) => TPlan; expected: TPlan };
  const cases: TCase[] = [
    {
      name: "the owner's plan: chain 6 moved later by more than the room takes chain 7 and side 1 along",
      before: CHAIN_PLAN,
      operate: (plan) => moveTask(plan, "chain 6", "2027-08-29"),
      expected: getChainPlan("2027-09-13", { "chain 5>chain 6": 41 }),
    },
    {
      name: "the owner's plan: chain 6 moved later within the room of the in 14 d moves nothing else",
      before: CHAIN_PLAN,
      operate: (plan) => moveTask(plan, "chain 6", "2027-08-26"),
      expected: getChainPlan("2027-09-10", { "chain 5>chain 6": 38 }),
    },
    {
      name: "the owner's plan: the n of the in 14 d turned up beyond the room does the same",
      before: CHAIN_PLAN,
      operate: (plan) => changeArrow(plan, "chain 6>chain 7", { delay: 17 }),
      expected: getChainPlan("2027-09-11", { "chain 6>chain 7": 17 }),
    },
    {
      name: "the owner's plan: chain 5 moved later pushes through two arrows before it meets the link",
      before: CHAIN_PLAN,
      operate: (plan) => moveTask(plan, "chain 5", "2027-07-12"),
      expected: getChainPlan("2027-09-13", { "chain 4>chain 5": 41 }),
    },
    {
      name: "a fixed task the link leads from gets another day, by the days the link would be apart",
      before: PLAN,
      operate: (plan) => moveTask(plan, "X", day(6)),
      expected: getPlan({ X: fixed("X", 6, 3), A: fixed("A", 10, 6) }),
    },
    {
      name: "an end dragged later pushes as a move does",
      before: PLAN,
      operate: (plan) => resizeTask(plan, "X", "end", day(8)),
      expected: getPlan({ X: fixed("X", 1, 8), A: fixed("A", 10, 6) }),
    },
    {
      name: "a task that follows and that the link leads from has the n of its deciding in n d grow",
      before: getPlan({ A: following("A", 6), Y: fixed("Y", 1, 2) }, { YA: arrow("Y>A", "end-start", 5) }),
      operate: (plan) => moveTask(plan, "X", day(6)),
      expected: getPlan(
        { X: fixed("X", 6, 3), A: following("A", 6), Y: fixed("Y", 1, 2) },
        { YA: arrow("Y>A", "end-start", 7) }
      ),
    },
    {
      name: "a link pulled from the other side: the task it leads from stays back, and the in n d it followed grows",
      before: {
        tasks: [fixed("X", 1, 3), fixed("Y", 5, 2), following("A", 6), following("B", 4)],
        arrows: [arrow("X>B", "end-start", 5), arrow("Y>A", "end-start", 1), arrow("A>B", "end-end", "linked")],
      },
      operate: (plan) => moveTask(plan, "Y", day(1)),
      expected: {
        tasks: [fixed("X", 1, 3), fixed("Y", 1, 2), following("A", 6), following("B", 4)],
        arrows: [arrow("X>B", "end-start", 5), arrow("Y>A", "end-start", 4), arrow("A>B", "end-end", "linked")],
      },
    },
    {
      name: "a body that goes later pushes on, and the next link that would open brings its own task later",
      before: getPlan({ E: following("E", 2), F: fixed("F", 15, 6) }, LINKED_ON),
      operate: (plan) => moveTask(plan, "X", day(6)),
      expected: getPlan(
        { X: fixed("X", 6, 3), A: fixed("A", 10, 6), E: following("E", 2), F: fixed("F", 17, 6) },
        LINKED_ON
      ),
    },
    {
      name: "a link that was apart before the operation is left as it is",
      before: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 5)],
      },
      operate: (plan) => changeArrow(plan, "X>B", { delay: 7 }),
      expected: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 7)],
      },
    },
    {
      name: "an arrow that the operation turns into in n d is no link any more",
      before: PLAN,
      operate: (plan) => moveTask(setArrowMode(plan, "A>B", "in"), "X", day(6)),
      expected: getPlan({ X: fixed("X", 6, 3) }, { AB: arrow("A>B", "end-end", 0) }),
    },
    {
      name: "an arrow whose next task the operation fixes on a day is a check, and no link any more",
      before: PLAN,
      operate: (plan) => fixNextTask(plan, "X>B", day(15)),
      expected: getPlan({ B: fixed("B", 15, 4) }),
    },
    {
      name: "an arrow that the operation removes holds nothing",
      before: PLAN,
      operate: (plan) => moveTask(removeArrow(plan, "A>B"), "X", day(6)),
      expected: { tasks: getPlan({ X: fixed("X", 6, 3) }).tasks, arrows: [ARROWS.XB, ARROWS.AC, ARROWS.CD] },
    },
    {
      name: "a round: an arrow drawn from the body to the task it is linked to pushes the task on as the body comes",
      before: PLAN,
      operate: (plan) => addArrow(plan, "D", "B", "end-start") as TPlan,
      expected: { tasks: PLAN.tasks, arrows: [...PLAN.arrows, { ...arrow("D>B", "end-start", 0), id: "D:B" }] },
    },
    {
      name: "a round of links: a link turned so that the three cannot be together leaves them as the plan computes",
      before: LINKED_ROUND,
      operate: (plan) => changeArrow(plan, "P>M", { kind: "end-start" }),
      expected: {
        tasks: LINKED_ROUND.tasks,
        arrows: [
          arrow("P>N", "end-start", "linked"),
          arrow("P>M", "end-start", "linked"),
          arrow("M>N", "end-end", "linked"),
        ],
      },
    },
  ];

  it.each(cases)("$name", ({ before, operate, expected }) => {
    const actual = keepLinksTogether(before, operate(before)).plan;

    expect(actual).toEqual(expected);
  });

  it("no operation of the engine makes a link come apart", () => {
    // Arrows are drawn to and from S and L only, which stand apart: an arrow between tasks that arrows connect
    // already can close a round, which the cases above are for.
    const plan = MIXED_PLAN;
    const linkIds = new Set(plan.arrows.flatMap(({ id, delay }) => (delay === "linked" ? [id] : [])));
    const connectedIds = plan.tasks.map((task) => task.id).filter((id) => id !== "S" && id !== "L");
    const days = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28].map(day);
    const kinds: TArrowKind[] = ["end-start", "start-start", "end-end"];
    const edges: TTaskEdge[] = ["start", "end"];
    const modes: TArrowMode[] = ["linked", "in", "on"];
    const operations: { name: string; run: () => TPlan | TRefusal }[] = [
      ...plan.tasks.flatMap(({ id }) => [
        ...days.flatMap((to) => [
          { name: `moveTask ${id} ${to}`, run: () => moveTask(plan, id, to) },
          ...edges.map((edge) => ({
            name: `resizeTask ${id} ${edge} ${to}`,
            run: () => resizeTask(plan, id, edge, to),
          })),
          { name: `placeTask ${id} ${to}`, run: () => placeTask(plan, id, to) },
        ]),
        { name: `removeTask ${id}`, run: () => removeTask(plan, id) },
      ]),
      ...connectedIds.flatMap((id) =>
        ["S", "L"].flatMap((apartId) =>
          [
            [id, apartId],
            [apartId, id],
          ].flatMap(([previousId, nextId]) =>
            kinds.flatMap((kind) =>
              [undefined, "linked" as const, 2].map((delay) => ({
                name: `addArrow ${previousId}>${nextId} ${kind} ${delay}`,
                run: () => addArrow(plan, previousId, nextId, kind, delay),
              }))
            )
          )
        )
      ),
      ...plan.arrows.flatMap(({ id }) => [
        ...kinds.map((kind) => ({ name: `changeArrow ${id} ${kind}`, run: () => changeArrow(plan, id, { kind }) })),
        ...([0, 2, 6, 12, "linked"] as const).map((delay) => ({
          name: `changeArrow ${id} ${delay}`,
          run: () => changeArrow(plan, id, { delay }),
        })),
        ...modes.map((mode) => ({ name: `setArrowMode ${id} ${mode}`, run: () => setArrowMode(plan, id, mode) })),
        ...([1, -1] as const).map((direction) => ({
          name: `turnArrowMode ${id} ${direction}`,
          run: () => turnArrowMode(plan, id, direction),
        })),
        { name: `removeArrow ${id}`, run: () => removeArrow(plan, id) },
        ...days.map((to) => ({ name: `fixNextTask ${id} ${to}`, run: () => fixNextTask(plan, id, to) })),
      ]),
      ...computeSchedule(plan.tasks, plan.arrows).conflicts.flatMap((conflict) =>
        conflict.waysOut.map((wayOut) => ({
          name: `applyWayOut ${conflict.arrowId} ${wayOut.way}`,
          run: () => applyWayOut(plan, conflict, wayOut),
        }))
      ),
    ];

    const actual = operations.flatMap(({ name, run }) => {
      const after = run();
      if ("refused" in after) return [];
      const apartLinks = keepLinksTogether(plan, after).schedule.apartLinks.filter((link) => linkIds.has(link.arrowId));
      return apartLinks.length > 0 ? [`${name}: ${apartLinks.map((link) => link.arrowId).join()}`] : [];
    });

    expect(actual).toEqual([]);
  });
});
