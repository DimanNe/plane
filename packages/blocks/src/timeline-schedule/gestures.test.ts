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
  getArrowKind,
  moveTask,
  placeTask,
  removeArrow,
  resizeTask,
} from "./gestures";
import { arrow, day, fixed, following } from "./test-helpers";
import type { TArrowKind, TPlan, TRefusal, TTaskEdge, TWayOut } from "./types";

describe("moveTask", () => {
  const cases: { name: string; plan: TPlan; taskId: string; dayOfMonth: number; expected: TPlan }[] = [
    {
      name: "a fixed task goes to the day and keeps its duration",
      plan: { tasks: [fixed("A", 1, 3)], arrows: [] },
      taskId: "A",
      dayOfMonth: 5,
      expected: { tasks: [fixed("A", 5, 3)], arrows: [] },
    },
    {
      name: "a fixed task goes to the day whatever its arrows ask for",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 6, 2)], arrows: [arrow("A>B", "end-start")] },
      taskId: "B",
      dayOfMonth: 2,
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 2, 2)], arrows: [arrow("A>B", "end-start")] },
    },
    {
      name: "of a task that follows its arrows the delay of the deciding arrow changes, so that it starts on the day",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start")] },
      taskId: "B",
      dayOfMonth: 7,
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 3)] },
    },
    {
      name: "a task that follows its arrows goes no earlier than immediately on its deciding arrow",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 2)] },
      taskId: "B",
      dayOfMonth: 2,
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start")] },
    },
    {
      name: "a task that follows its arrows goes no earlier than its other arrows ask for, and they keep their delay",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 4), arrow("C>B", "end-start", 2)],
      },
      taskId: "B",
      dayOfMonth: 3,
      expected: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 1), arrow("C>B", "end-start", 2)],
      },
    },
    {
      name: "a deciding end -> end arrow gets the delay that lets the task start on the day",
      plan: { tasks: [fixed("A", 1, 5), following("B", 2)], arrows: [arrow("A>B", "end-end")] },
      taskId: "B",
      dayOfMonth: 6,
      expected: { tasks: [fixed("A", 1, 5), following("B", 2)], arrows: [arrow("A>B", "end-end", 2)] },
    },
  ];

  it.each(cases)("$name", ({ plan, taskId, dayOfMonth, expected }) => {
    const actual = moveTask(plan, taskId, day(dayOfMonth));

    expect(actual).toEqual(expected);
  });
});

describe("resizeTask", () => {
  const followingStartArrow: TPlan = {
    tasks: [fixed("A", 1, 3), following("B", 3)],
    arrows: [arrow("A>B", "end-start")],
  };
  const followingEndArrow: TPlan = {
    tasks: [fixed("A", 1, 5), following("B", 2)],
    arrows: [arrow("A>B", "end-end")],
  };
  const cases: { name: string; plan: TPlan; edge: TTaskEdge; toDay: string; expected: TPlan }[] = [
    {
      name: "the end edge of a fixed task changes its duration",
      plan: { tasks: [fixed("B", 1, 3)], arrows: [] },
      edge: "end",
      toDay: day(6),
      expected: { tasks: [fixed("B", 1, 6)], arrows: [] },
    },
    {
      name: "the end edge stops where the task is one day long",
      plan: { tasks: [fixed("B", 1, 3)], arrows: [] },
      edge: "end",
      toDay: "2025-12-20",
      expected: { tasks: [fixed("B", 1, 1)], arrows: [] },
    },
    {
      name: "the start edge of a fixed task changes its day and keeps its end",
      plan: { tasks: [fixed("B", 1, 3)], arrows: [] },
      edge: "start",
      toDay: day(2),
      expected: { tasks: [fixed("B", 2, 2)], arrows: [] },
    },
    {
      name: "the start edge stops where the task is one day long",
      plan: { tasks: [fixed("B", 1, 3)], arrows: [] },
      edge: "start",
      toDay: day(9),
      expected: { tasks: [fixed("B", 3, 1)], arrows: [] },
    },
    {
      name: "the start edge of a task decided by an arrow to its start changes that arrow's delay and keeps the end",
      plan: followingStartArrow,
      edge: "start",
      toDay: day(5),
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 1)] },
    },
    {
      name: "the start edge of a task that follows its arrows goes no earlier than immediately on the deciding arrow",
      plan: followingStartArrow,
      edge: "start",
      toDay: day(1),
      expected: followingStartArrow,
    },
    {
      name: "the end edge of a task decided by an arrow to its start changes only its duration",
      plan: followingStartArrow,
      edge: "end",
      toDay: day(8),
      expected: { tasks: [fixed("A", 1, 3), following("B", 5)], arrows: [arrow("A>B", "end-start")] },
    },
    {
      name: "the end edge of a task decided by an end -> end arrow changes that arrow's delay and keeps the start",
      plan: followingEndArrow,
      edge: "end",
      toDay: day(7),
      expected: { tasks: [fixed("A", 1, 5), following("B", 4)], arrows: [arrow("A>B", "end-end", 2)] },
    },
    {
      name: "the start edge of a task decided by an end -> end arrow changes only its duration",
      plan: followingEndArrow,
      edge: "start",
      toDay: day(2),
      expected: { tasks: [fixed("A", 1, 5), following("B", 4)], arrows: [arrow("A>B", "end-end")] },
    },
    {
      name: "the end edge goes no earlier than another end -> end arrow asks for",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 6), following("B", 5)],
        arrows: [arrow("A>B", "end-start"), arrow("C>B", "end-end")],
      },
      edge: "end",
      toDay: day(5),
      expected: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 6), following("B", 3)],
        arrows: [arrow("A>B", "end-start"), arrow("C>B", "end-end")],
      },
    },
  ];

  it.each(cases)("$name", ({ plan, edge, toDay, expected }) => {
    const actual = resizeTask(plan, "B", edge, toDay);

    expect(actual).toEqual(expected);
  });
});

describe("placeTask", () => {
  const cases: { name: string; plan: TPlan; expected: TPlan }[] = [
    {
      name: "a work item that was not on the timeline becomes a task fixed on the day, one day long",
      plan: { tasks: [fixed("A", 1, 3)], arrows: [] },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 9, 1)], arrows: [] },
    },
    {
      name: "a task is fixed on the day and keeps its duration, also when it followed its arrows",
      plan: { tasks: [fixed("A", 1, 3), following("B", 4)], arrows: [arrow("A>B", "end-start")] },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 9, 4)], arrows: [arrow("A>B", "end-start")] },
    },
  ];

  it.each(cases)("$name", ({ plan, expected }) => {
    const actual = placeTask(plan, "B", day(9));

    expect(actual).toEqual(expected);
  });
});

describe("addArrow", () => {
  const cases: { name: string; plan: TPlan; previousId: string; nextId: string; expected: TPlan | TRefusal }[] = [
    {
      name: "a new arrow asks immediately, and its next task follows its arrows from then on",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 1, 2)], arrows: [] },
      previousId: "A",
      nextId: "B",
      expected: {
        tasks: [fixed("A", 1, 3), following("B", 2)],
        arrows: [{ id: "A:B", previousId: "A", nextId: "B", kind: "start-start", delay: 0 }],
      },
    },
    {
      name: "a second arrow into a task from another chain is not a loop",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 1), following("B", 2)],
        arrows: [arrow("A>B", "end-start"), arrow("A>C", "end-start")],
      },
      previousId: "C",
      nextId: "B",
      expected: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 1), following("B", 2)],
        arrows: [
          arrow("A>B", "end-start"),
          arrow("A>C", "end-start"),
          { id: "C:B", previousId: "C", nextId: "B", kind: "start-start", delay: 0 },
        ],
      },
    },
    {
      name: "an arrow from a task to itself is refused",
      plan: { tasks: [fixed("A", 1, 3)], arrows: [] },
      previousId: "A",
      nextId: "A",
      expected: { refused: "same-task" },
    },
    {
      name: "a second arrow between two tasks in the same direction is refused",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-end")] },
      previousId: "A",
      nextId: "B",
      expected: { refused: "already-connected" },
    },
    {
      name: "an arrow against an arrow is refused as a loop",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start")] },
      previousId: "B",
      nextId: "A",
      expected: { refused: "loop" },
    },
    {
      name: "an arrow back to a task further up its chain is refused as a loop",
      plan: {
        tasks: [fixed("A", 1, 3), following("B", 2), following("C", 2)],
        arrows: [arrow("A>B", "end-start"), arrow("B>C", "end-start")],
      },
      previousId: "C",
      nextId: "A",
      expected: { refused: "loop" },
    },
  ];

  it.each(cases)("$name", ({ plan, previousId, nextId, expected }) => {
    const actual = addArrow(plan, previousId, nextId, "start-start");

    expect(actual).toEqual(expected);
  });
});

describe("changeArrow", () => {
  const plan: TPlan = { tasks: [fixed("A", 1, 3), fixed("B", 9, 2)], arrows: [arrow("A>B", "end-start", 1)] };
  const cases: { name: string; change: { kind?: TArrowKind; delay?: number }; expected: TPlan }[] = [
    {
      name: "a delay is set on the arrow and makes its next task follow its arrows",
      change: { delay: 4 },
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 4)] },
    },
    {
      name: "the delay immediately is set as any other",
      change: { delay: 0 },
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 0)] },
    },
    {
      name: "a kind alone changes the arrow and leaves its delay and its next task as they are",
      change: { kind: "end-end" },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 9, 2)], arrows: [arrow("A>B", "end-end", 1)] },
    },
  ];

  it.each(cases)("$name", ({ change, expected }) => {
    const actual = changeArrow(plan, "A>B", change);

    expect(actual).toEqual(expected);
  });
});

describe("removeArrow", () => {
  const cases: { name: string; plan: TPlan; expected: TPlan }[] = [
    {
      name: "a task that followed only the removed arrow is fixed on the day it stood on",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 1)] },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 5, 2)], arrows: [] },
    },
    {
      name: "a task with another arrow goes on following its arrows",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 1), following("B", 2)],
        arrows: [arrow("A>B", "end-start"), arrow("C>B", "end-start")],
      },
      expected: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 1), following("B", 2)],
        arrows: [arrow("C>B", "end-start")],
      },
    },
    {
      name: "an arrow from a work item that is not on the timeline is none to follow",
      plan: {
        tasks: [fixed("A", 1, 3), following("B", 2)],
        arrows: [arrow("A>B", "end-start"), arrow("X>B", "end-start")],
      },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 4, 2)], arrows: [arrow("X>B", "end-start")] },
    },
    {
      name: "a fixed task stays fixed on its day",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 9, 2)], arrows: [arrow("A>B", "end-start")] },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 9, 2)], arrows: [] },
    },
  ];

  it.each(cases)("$name", ({ plan, expected }) => {
    const actual = removeArrow(plan, "A>B");

    expect(actual).toEqual(expected);
  });
});

describe("fixNextTask", () => {
  const cases: { name: string; kind: TArrowKind; expected: TPlan }[] = [
    {
      name: "the next task of an arrow to its start is fixed to start on the day",
      kind: "end-start",
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 10, 3)], arrows: [arrow("A>B", "end-start")] },
    },
    {
      name: "the next task of an end -> end arrow is fixed to end on the day",
      kind: "end-end",
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 8, 3)], arrows: [arrow("A>B", "end-end")] },
    },
  ];

  it.each(cases)("$name", ({ kind, expected }) => {
    const plan: TPlan = { tasks: [fixed("A", 1, 3), following("B", 3)], arrows: [arrow("A>B", kind)] };

    const actual = fixNextTask(plan, "A>B", day(10));

    expect(actual).toEqual(expected);
  });
});

describe("applyWayOut", () => {
  // the arrow asks B to start on day 6, two days after the day it is fixed on
  const plan: TPlan = { tasks: [fixed("A", 1, 3), fixed("B", 4, 2)], arrows: [arrow("A>B", "end-start", 2)] };
  const cases: { name: string; wayOut: TWayOut; expected: TPlan }[] = [
    {
      name: "the task follows its arrows",
      wayOut: { way: "follow-arrows" },
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 2)] },
    },
    {
      name: "the fixed day moves to the day asked for",
      wayOut: { way: "move-fixed-day", day: day(6) },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 6, 2)], arrows: [arrow("A>B", "end-start", 2)] },
    },
    {
      name: "the arrow gets the shorter delay and the task stays fixed",
      wayOut: { way: "shorten-delay", delay: 0 },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 4, 2)], arrows: [arrow("A>B", "end-start", 0)] },
    },
    {
      name: "the arrow is removed",
      wayOut: { way: "remove-arrow" },
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 4, 2)], arrows: [] },
    },
  ];

  it.each(cases)("$name", ({ wayOut, expected }) => {
    const [conflict] = computeSchedule(plan.tasks, plan.arrows).conflicts;

    const actual = applyWayOut(plan, conflict, wayOut);

    expect(actual).toEqual(expected);
  });

  it("every way out that a conflict offers leaves no conflict", () => {
    const [conflict] = computeSchedule(plan.tasks, plan.arrows).conflicts;

    const actual = conflict.waysOut.map((wayOut) => {
      const changed = applyWayOut(plan, conflict, wayOut);
      return { way: wayOut.way, conflicts: computeSchedule(changed.tasks, changed.arrows).conflicts };
    });

    expect(actual).toEqual([
      { way: "follow-arrows", conflicts: [] },
      { way: "move-fixed-day", conflicts: [] },
      { way: "shorten-delay", conflicts: [] },
      { way: "remove-arrow", conflicts: [] },
    ]);
  });
});

describe("getArrowKind", () => {
  const cases: { previousEdge: TTaskEdge; nextEdge: TTaskEdge; expected: TArrowKind | undefined }[] = [
    { previousEdge: "end", nextEdge: "start", expected: "end-start" },
    { previousEdge: "start", nextEdge: "start", expected: "start-start" },
    { previousEdge: "end", nextEdge: "end", expected: "end-end" },
    { previousEdge: "start", nextEdge: "end", expected: undefined },
  ];

  it.each(cases)("from the $previousEdge of a bar to the $nextEdge of another: $expected", (testCase) => {
    const actual = getArrowKind(testCase.previousEdge, testCase.nextEdge);

    expect(actual).toEqual(testCase.expected);
  });
});

describe("every gesture", () => {
  const plan: TPlan = {
    tasks: [fixed("A", 1, 3), fixed("C", 1, 2), following("B", 2), fixed("D", 1, 1)],
    arrows: [arrow("A>B", "end-start", 4), arrow("C>B", "end-end"), arrow("A>D", "end-start")],
  };
  const [conflict] = computeSchedule(plan.tasks, plan.arrows).conflicts;
  const gestures: { name: string; run: (given: TPlan) => unknown }[] = [
    { name: "moveTask", run: (given) => moveTask(given, "B", day(12)) },
    { name: "resizeTask", run: (given) => resizeTask(given, "B", "end", day(12)) },
    { name: "placeTask", run: (given) => placeTask(given, "B", day(12)) },
    { name: "addArrow", run: (given) => addArrow(given, "A", "C", "end-start") },
    { name: "changeArrow", run: (given) => changeArrow(given, "A>B", { delay: 1, kind: "start-start" }) },
    { name: "removeArrow", run: (given) => removeArrow(given, "A>B") },
    { name: "fixNextTask", run: (given) => fixNextTask(given, "A>B", day(12)) },
    { name: "applyWayOut", run: (given) => applyWayOut(given, conflict, { way: "follow-arrows" }) },
  ];

  it.each(gestures)("$name leaves the plan it is given as it was", ({ run }) => {
    const given = structuredClone(plan);

    run(given);

    expect(given).toEqual(plan);
  });
});
