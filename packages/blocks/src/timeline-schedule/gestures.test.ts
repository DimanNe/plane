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
  getTaskMove,
  getTaskResize,
  moveTask,
  placeTask,
  removeArrow,
  getArrowMode,
  getLatestArrowId,
  removeTask,
  resizeTask,
  setArrowMode,
  turnArrowMode,
} from "./gestures";
import { arrow, day, fixed, following } from "./test-helpers";
import type { TArrowDelay, TArrowKind, TArrowMode, TPlan, TRefusal, TTaskEdge, TTaskMove, TWayOut } from "./types";

// X ends on the 7th and asks B to start in 2 d, on the 10th. A is fixed from the 12th to the 14th and B is linked to
// its end: the body of A and B stands 5 days later than the in n d asks, and 7 days after the end of X.
const BODY_BEHIND_IN_DAYS: TPlan = {
  tasks: [fixed("X", 5, 3), fixed("A", 12, 3), following("B", 2)],
  arrows: [arrow("X>B", "end-start", 2), arrow("A>B", "end-start", "linked")],
};
const BODY_AT_IN_0_DAYS: TPlan = {
  tasks: [fixed("X", 5, 3), fixed("A", 5, 3), following("B", 2)],
  arrows: [arrow("X>B", "end-start", 0), arrow("A>B", "end-start", "linked")],
};

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
      name: "every in n d to a task gives the days the task stands later than it asks, then its n, and the first at 0 stops the move",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 4), arrow("C>B", "end-start", 2)],
      },
      taskId: "B",
      dayOfMonth: 3,
      expected: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 0), arrow("C>B", "end-start", 1)],
      },
    },
    {
      name: "an in n d that the task still stands later than keeps its n",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 4), arrow("C>B", "end-start", 2)],
      },
      taskId: "B",
      dayOfMonth: 6,
      expected: {
        tasks: [fixed("A", 1, 3), fixed("C", 1, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 2), arrow("C>B", "end-start", 2)],
      },
    },
    {
      name: "a deciding end -> end arrow gets the delay that lets the task start on the day",
      plan: { tasks: [fixed("A", 1, 5), following("B", 2)], arrows: [arrow("A>B", "end-end")] },
      taskId: "B",
      dayOfMonth: 6,
      expected: { tasks: [fixed("A", 1, 5), following("B", 2)], arrows: [arrow("A>B", "end-end", 2)] },
    },
    {
      name: "a task that is linked takes the fixed task it is linked to along, later, and the arrow stays linked",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] },
      taskId: "B",
      dayOfMonth: 7,
      expected: { tasks: [fixed("A", 4, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] },
    },
    {
      name: "a task that is linked takes the fixed task it is linked to along, earlier",
      plan: { tasks: [fixed("A", 5, 3), following("B", 2)], arrows: [arrow("A>B", "end-end", "linked")] },
      taskId: "B",
      dayOfMonth: 2,
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-end", "linked")] },
    },
    {
      name: "up a chain of linked tasks the task that is fixed on its day takes up the move",
      plan: {
        tasks: [fixed("A", 1, 3), following("B", 2), following("C", 4)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("B>C", "start-start", "linked")],
      },
      taskId: "C",
      dayOfMonth: 6,
      expected: {
        tasks: [fixed("A", 3, 3), following("B", 2), following("C", 4)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("B>C", "start-start", "linked")],
      },
    },
    {
      name: "up a chain of linked tasks an in n d takes up the move: its n changes and the task before it stays",
      plan: {
        tasks: [fixed("A", 1, 3), following("B", 2), following("C", 4)],
        arrows: [arrow("A>B", "end-start", 2), arrow("B>C", "end-start", "linked")],
      },
      taskId: "C",
      dayOfMonth: 11,
      expected: {
        tasks: [fixed("A", 1, 3), following("B", 2), following("C", 4)],
        arrows: [arrow("A>B", "end-start", 5), arrow("B>C", "end-start", "linked")],
      },
    },
    {
      name: "the move stops where an in n d up the chain would go under 0",
      plan: {
        tasks: [fixed("A", 1, 3), following("B", 2), following("C", 4)],
        arrows: [arrow("A>B", "end-start", 2), arrow("B>C", "end-start", "linked")],
      },
      taskId: "C",
      dayOfMonth: 1,
      expected: {
        tasks: [fixed("A", 1, 3), following("B", 2), following("C", 4)],
        arrows: [arrow("A>B", "end-start", 0), arrow("B>C", "end-start", "linked")],
      },
    },
    {
      name: "an in n d into a linked task takes up the move with the task it is linked to, and stops both at in 0 d",
      plan: BODY_BEHIND_IN_DAYS,
      taskId: "B",
      dayOfMonth: 5,
      expected: BODY_AT_IN_0_DAYS,
    },
    {
      name: "moving the task a link leads from does what moving the linked task does",
      plan: BODY_BEHIND_IN_DAYS,
      taskId: "A",
      dayOfMonth: 2,
      expected: BODY_AT_IN_0_DAYS,
    },
    {
      name: "the body goes earlier by the days it stands later than an in n d asks, and that arrow keeps its n",
      plan: BODY_BEHIND_IN_DAYS,
      taskId: "A",
      dayOfMonth: 8,
      expected: {
        tasks: [fixed("X", 5, 3), fixed("A", 8, 3), following("B", 2)],
        arrows: [arrow("X>B", "end-start", 2), arrow("A>B", "end-start", "linked")],
      },
    },
    {
      name: "a body moved later is held by its fixed task, and an in n d into it keeps its n",
      plan: {
        tasks: [fixed("A", 5, 3), fixed("X", 1, 3), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 4)],
      },
      taskId: "B",
      dayOfMonth: 10,
      expected: {
        tasks: [fixed("A", 7, 3), fixed("X", 1, 3), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 4)],
      },
    },
    {
      name: "an in n d into a task further down the links stops the move of the task they begin at",
      plan: {
        tasks: [fixed("Y", 5, 2), fixed("A", 10, 2), following("B", 2), following("C", 2)],
        arrows: [
          arrow("A>B", "end-start", "linked"),
          arrow("B>C", "end-start", "linked"),
          arrow("Y>C", "end-start", 3),
        ],
      },
      taskId: "A",
      dayOfMonth: 1,
      expected: {
        tasks: [fixed("Y", 5, 2), fixed("A", 3, 2), following("B", 2), following("C", 2)],
        arrows: [
          arrow("A>B", "end-start", "linked"),
          arrow("B>C", "end-start", "linked"),
          arrow("Y>C", "end-start", 0),
        ],
      },
    },
    {
      name: "a linked arrow and an in n d that hold the task on the same day both take up a move earlier",
      plan: {
        tasks: [fixed("A", 5, 3), fixed("X", 1, 3), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 4)],
      },
      taskId: "B",
      dayOfMonth: 6,
      expected: {
        tasks: [fixed("A", 3, 3), fixed("X", 1, 3), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 2)],
      },
    },
    {
      name: "a task that two linked arrows hold takes both their tasks along",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("X", 2, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", "linked")],
      },
      taskId: "B",
      dayOfMonth: 7,
      expected: {
        tasks: [fixed("A", 4, 3), fixed("X", 5, 2), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", "linked")],
      },
    },
    {
      name: "two linked chains that meet in one task move that task once",
      plan: {
        tasks: [fixed("R", 1, 2), following("A", 3), following("X", 3), following("B", 2)],
        arrows: [
          arrow("R>A", "start-start", "linked"),
          arrow("R>X", "start-start", "linked"),
          arrow("A>B", "end-start", "linked"),
          arrow("X>B", "end-start", "linked"),
        ],
      },
      taskId: "B",
      dayOfMonth: 6,
      expected: {
        tasks: [fixed("R", 3, 2), following("A", 3), following("X", 3), following("B", 2)],
        arrows: [
          arrow("R>A", "start-start", "linked"),
          arrow("R>X", "start-start", "linked"),
          arrow("A>B", "end-start", "linked"),
          arrow("X>B", "end-start", "linked"),
        ],
      },
    },
    {
      name: "a link that is apart lets the task go earlier until its edges are together",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 3), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 5)],
      },
      taskId: "B",
      dayOfMonth: 2,
      expected: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 3), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 0)],
      },
    },
    {
      name: "the task a link leads from takes the linked task along, and nothing is changed for it",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] },
      taskId: "A",
      dayOfMonth: 4,
      expected: { tasks: [fixed("A", 4, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] },
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
  const linkedAtStart: TPlan = {
    tasks: [fixed("A", 1, 3), following("B", 3)],
    arrows: [arrow("A>B", "end-start", "linked")],
  };
  const linkedAtEnd: TPlan = {
    tasks: [fixed("A", 1, 5), following("B", 2)],
    arrows: [arrow("A>B", "end-end", "linked")],
  };
  const cases: { name: string; plan: TPlan; edge: TTaskEdge; toDay: string; expected: TPlan }[] = [
    {
      name: "the start edge that a link holds takes the task it is linked to along, and the end stays",
      plan: linkedAtStart,
      edge: "start",
      toDay: day(5),
      expected: { tasks: [fixed("A", 2, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] },
    },
    {
      name: "the end edge of a task that is linked at its start changes only its duration",
      plan: linkedAtStart,
      edge: "end",
      toDay: day(8),
      expected: { tasks: [fixed("A", 1, 3), following("B", 5)], arrows: [arrow("A>B", "end-start", "linked")] },
    },
    {
      name: "the end edge that a link holds takes the task it is linked to along, and the start stays",
      plan: linkedAtEnd,
      edge: "end",
      toDay: day(7),
      expected: { tasks: [fixed("A", 3, 5), following("B", 4)], arrows: [arrow("A>B", "end-end", "linked")] },
    },
    {
      name: "the start edge of a task that is linked at its end changes only its duration",
      plan: linkedAtEnd,
      edge: "start",
      toDay: day(2),
      expected: { tasks: [fixed("A", 1, 5), following("B", 4)], arrows: [arrow("A>B", "end-end", "linked")] },
    },
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

describe("getTaskMove and getTaskResize", () => {
  // a chain of links whose last task has its other edge joined to the first one: P -> N, P -> M, M -> N
  const LINKED_ROUND: TPlan = {
    tasks: [fixed("P", 1, 3), following("M", 6), following("N", 3)],
    arrows: [
      arrow("P>N", "end-start", "linked"),
      arrow("P>M", "start-start", "linked"),
      arrow("M>N", "end-end", "linked"),
    ],
  };

  type TCase = { name: string; move: () => TTaskMove; expected: TTaskMove };
  const cases: TCase[] = [
    {
      name: "an in n d that is at 0 stops a move that was asked to go further",
      move: () => getTaskMove(BODY_BEHIND_IN_DAYS, "A", day(2)),
      expected: { plan: BODY_AT_IN_0_DAYS, stoppingArrowIds: ["X>B"] },
    },
    {
      name: "a move that goes exactly as far as an in n d lets it is stopped by nothing",
      move: () => getTaskMove(BODY_BEHIND_IN_DAYS, "A", day(5)),
      expected: { plan: BODY_AT_IN_0_DAYS, stoppingArrowIds: [] },
    },
    {
      name: "a link that is apart stops the move where its edges come together",
      move: () =>
        getTaskMove(
          {
            tasks: [fixed("A", 1, 3), fixed("X", 1, 2), following("B", 2)],
            arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 5)],
          },
          "B",
          day(2)
        ),
      expected: {
        plan: {
          tasks: [fixed("A", 1, 3), fixed("X", 1, 2), following("B", 2)],
          arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 1)],
        },
        stoppingArrowIds: ["A>B"],
      },
    },
    {
      name: "the edge a link leads from stops where an in n d into the linked task is at 0, and that arrow stops it",
      move: () =>
        getTaskResize(
          {
            tasks: [fixed("X", 5, 3), fixed("A", 6, 6), following("B", 2)],
            arrows: [arrow("X>B", "end-start", 3), arrow("A>B", "end-start", "linked")],
          },
          "A",
          "end",
          day(6)
        ),
      expected: {
        plan: {
          tasks: [fixed("X", 5, 3), fixed("A", 6, 2), following("B", 2)],
          arrows: [arrow("X>B", "end-start", 0), arrow("A>B", "end-start", "linked")],
        },
        stoppingArrowIds: ["X>B"],
      },
    },
    {
      name: "an edge that stops where its task is one day long is stopped by no arrow",
      move: () => getTaskResize(BODY_BEHIND_IN_DAYS, "A", "end", day(5)),
      expected: {
        plan: {
          tasks: [fixed("X", 5, 3), fixed("A", 12, 1), following("B", 2)],
          arrows: [arrow("X>B", "end-start", 2), arrow("A>B", "end-start", "linked")],
        },
        stoppingArrowIds: [],
      },
    },
    {
      name: "the start edge of a task goes earlier by the days of an in n d to it, while a link holds its end",
      move: () =>
        getTaskResize(
          {
            tasks: [fixed("X", 1, 2), fixed("A", 5, 6), following("B", 3)],
            arrows: [arrow("X>B", "end-start", 2), arrow("A>B", "end-end", "linked")],
          },
          "B",
          "start",
          day(1)
        ),
      expected: {
        plan: {
          tasks: [fixed("X", 1, 2), fixed("A", 5, 6), following("B", 8)],
          arrows: [arrow("X>B", "end-start", 0), arrow("A>B", "end-end", "linked")],
        },
        stoppingArrowIds: ["X>B"],
      },
    },
    {
      name: "an edge does not move when links join its body to the other edge of its task",
      move: () => getTaskResize(LINKED_ROUND, "P", "end", day(5)),
      expected: { plan: LINKED_ROUND, stoppingArrowIds: [] },
    },
    {
      name: "the same task moves as a whole with all that is linked to it",
      move: () => getTaskMove(LINKED_ROUND, "P", day(3)),
      expected: {
        plan: { tasks: [fixed("P", 3, 3), following("M", 6), following("N", 3)], arrows: LINKED_ROUND.arrows },
        stoppingArrowIds: [],
      },
    },
  ];

  it.each(cases)("$name", ({ move, expected }) => {
    const actual = move();

    expect(actual).toEqual(expected);
  });

  it("no move of any task of a body, at any edge, to any day makes a link come apart", () => {
    // the owner's plan in small: an in n d and a fixed task both lead to one task, and two more are linked on
    const plan: TPlan = {
      tasks: [fixed("X", 1, 3), fixed("A", 8, 6), following("B", 4), following("C", 3), following("D", 2)],
      arrows: [
        arrow("X>B", "end-start", 3),
        arrow("A>B", "end-end", "linked"),
        arrow("A>C", "end-start", "linked"),
        arrow("C>D", "end-start", "linked"),
      ],
    };
    const moves = ["A", "B", "C", "D"].flatMap((taskId) =>
      [1, 4, 7, 10, 13, 16, 19, 22, 25].flatMap((dayOfMonth) => [
        getTaskMove(plan, taskId, day(dayOfMonth)),
        getTaskResize(plan, taskId, "start", day(dayOfMonth)),
        getTaskResize(plan, taskId, "end", day(dayOfMonth)),
      ])
    );

    const actual = moves.flatMap((move) => computeSchedule(move.plan.tasks, move.plan.arrows).apartLinks);

    expect(actual).toEqual([]);
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

describe("removeTask", () => {
  const cases: { name: string; plan: TPlan; taskId: string; expected: TPlan }[] = [
    {
      name: "a task without arrows leaves, and nothing else changes",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 9, 2)], arrows: [] },
      taskId: "A",
      expected: { tasks: [fixed("B", 9, 2)], arrows: [] },
    },
    {
      name: "its arrows leave with it, those that lead from it and those that lead to it",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("B", 9, 2), fixed("C", 20, 1), fixed("D", 1, 1)],
        arrows: [arrow("A>B", "end-start"), arrow("B>C", "end-start"), arrow("D>C", "start-start")],
      },
      taskId: "B",
      expected: {
        tasks: [fixed("A", 1, 3), fixed("C", 20, 1), fixed("D", 1, 1)],
        arrows: [arrow("D>C", "start-start")],
      },
    },
    {
      name: "a task that followed only it is fixed on the day it stood on",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 1)] },
      taskId: "A",
      expected: { tasks: [fixed("B", 5, 2)], arrows: [] },
    },
    {
      name: "a task that its other arrow would start earlier is fixed on the day it stood on, too",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 1), following("B", 2)],
        arrows: [arrow("A>B", "end-start"), arrow("X>B", "end-start")],
      },
      taskId: "A",
      expected: { tasks: [fixed("X", 1, 1), fixed("B", 4, 2)], arrows: [arrow("X>B", "end-start")] },
    },
    {
      name: "a task that another arrow holds on its day goes on following its arrows",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("X", 3, 1), following("B", 2)],
        arrows: [arrow("A>B", "end-start"), arrow("X>B", "end-start")],
      },
      taskId: "A",
      expected: { tasks: [fixed("X", 3, 1), following("B", 2)], arrows: [arrow("X>B", "end-start")] },
    },
    {
      name: "a task that followed its arrows leaves like any other, and the task after it stays",
      plan: {
        tasks: [fixed("A", 1, 3), following("B", 2), following("C", 1)],
        arrows: [arrow("A>B", "end-start"), arrow("B>C", "end-start")],
      },
      taskId: "B",
      expected: { tasks: [fixed("A", 1, 3), fixed("C", 6, 1)], arrows: [] },
    },
  ];

  it.each(cases)("$name", ({ plan, taskId, expected }) => {
    const actual = removeTask(plan, taskId);

    expect(actual).toEqual(expected);
  });

  it("no task stands on another day afterwards", () => {
    const plan: TPlan = {
      tasks: [fixed("A", 1, 3), fixed("X", 1, 1), following("B", 2), following("C", 1), following("D", 2)],
      arrows: [
        arrow("A>B", "end-start", 2),
        arrow("X>B", "end-start"),
        arrow("B>C", "end-start"),
        arrow("A>D", "start-start", 4),
      ],
    };
    const before = computeSchedule(plan.tasks, plan.arrows).dates;
    const expected = { X: before.X, B: before.B, C: before.C, D: before.D };

    const taken = removeTask(plan, "A");
    const actual = computeSchedule(taken.tasks, taken.arrows).dates;

    expect(actual).toEqual(expected);
  });
});

describe("addArrow", () => {
  const cases: {
    name: string;
    plan: TPlan;
    previousId: string;
    nextId: string;
    delay?: TArrowDelay;
    expected: TPlan | TRefusal;
  }[] = [
    {
      name: "a new arrow between edges that are together is in 0 d, and its next task follows its arrows from then on",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 1, 2)], arrows: [] },
      previousId: "A",
      nextId: "B",
      expected: {
        tasks: [fixed("A", 1, 3), following("B", 2)],
        arrows: [{ id: "A:B", previousId: "A", nextId: "B", kind: "start-start", delay: 0 }],
      },
    },
    {
      name: "a new arrow says the days there are between its edges, so that its next task stays where it is",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 6, 2)], arrows: [] },
      previousId: "A",
      nextId: "B",
      expected: {
        tasks: [fixed("A", 1, 3), following("B", 2)],
        arrows: [{ id: "A:B", previousId: "A", nextId: "B", kind: "start-start", delay: 5 }],
      },
    },
    {
      name: "a new arrow to a task that stands before its edge is in 0 d, which moves the task to the edge",
      plan: { tasks: [fixed("A", 4, 3), fixed("B", 1, 2)], arrows: [] },
      previousId: "A",
      nextId: "B",
      expected: {
        tasks: [fixed("A", 4, 3), following("B", 2)],
        arrows: [{ id: "A:B", previousId: "A", nextId: "B", kind: "start-start", delay: 0 }],
      },
    },
    {
      name: "a new arrow to a work item that is not on the timeline is in 0 d",
      plan: { tasks: [fixed("A", 4, 3)], arrows: [] },
      previousId: "A",
      nextId: "B",
      expected: {
        tasks: [fixed("A", 4, 3)],
        arrows: [{ id: "A:B", previousId: "A", nextId: "B", kind: "start-start", delay: 0 }],
      },
    },
    {
      name: "a new arrow that is given a delay asks that delay",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 1, 2)], arrows: [] },
      previousId: "A",
      nextId: "B",
      delay: 4,
      expected: {
        tasks: [fixed("A", 1, 3), following("B", 2)],
        arrows: [{ id: "A:B", previousId: "A", nextId: "B", kind: "start-start", delay: 4 }],
      },
    },
    {
      name: "a new arrow that is given as linked is linked, whatever days there are",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 6, 2)], arrows: [] },
      previousId: "A",
      nextId: "B",
      delay: "linked",
      expected: {
        tasks: [fixed("A", 1, 3), following("B", 2)],
        arrows: [{ id: "A:B", previousId: "A", nextId: "B", kind: "start-start", delay: "linked" }],
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
          { id: "C:B", previousId: "C", nextId: "B", kind: "start-start", delay: 3 },
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

  it.each(cases)("$name", ({ plan, previousId, nextId, delay, expected }) => {
    const actual = addArrow(plan, previousId, nextId, "start-start", delay);

    expect(actual).toEqual(expected);
  });
});

describe("getArrowMode", () => {
  const cases: { name: string; plan: TPlan; expected: TArrowMode }[] = [
    {
      name: "an arrow without a delay whose next task follows it is linked",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] },
      expected: "linked",
    },
    {
      name: "an arrow with a delay whose next task follows it is in n d, also with no days",
      plan: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 0)] },
      expected: "in",
    },
    {
      name: "an arrow whose next task is fixed on its day is on, whatever it asks",
      plan: { tasks: [fixed("A", 1, 3), fixed("B", 9, 2)], arrows: [arrow("A>B", "end-start", "linked")] },
      expected: "on",
    },
  ];

  it.each(cases)("$name", ({ plan, expected }) => {
    const actual = getArrowMode(plan, plan.arrows[0]);

    expect(actual).toEqual(expected);
  });
});

describe("setArrowMode", () => {
  const linked: TPlan = { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] };
  const inThreeDays: TPlan = { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 3)] };
  const onLaterDay: TPlan = { tasks: [fixed("A", 1, 3), fixed("B", 9, 2)], arrows: [arrow("A>B", "end-start", 1)] };
  const onEarlierDay: TPlan = { tasks: [fixed("A", 1, 3), fixed("B", 2, 2)], arrows: [arrow("A>B", "end-start", 1)] };
  const cases: { name: string; plan: TPlan; mode: TArrowMode; expected: TPlan }[] = [
    {
      name: "linked to in gives in 0 d, which moves nothing",
      plan: linked,
      mode: "in",
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 0)] },
    },
    {
      name: "a link that is apart, turned to in, says the days it is apart, which moves nothing either",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 6), following("B", 2)],
        arrows: [arrow("A>B", "end-start", "linked"), arrow("X>B", "end-start", 1)],
      },
      mode: "in",
      expected: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 6), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 4), arrow("X>B", "end-start", 1)],
      },
    },
    {
      name: "linked to on fixes the task on the day it stands on, and the arrow is still linked underneath",
      plan: linked,
      mode: "on",
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 4, 2)], arrows: [arrow("A>B", "end-start", "linked")] },
    },
    {
      name: "in to linked brings the edges together",
      plan: inThreeDays,
      mode: "linked",
      expected: linked,
    },
    {
      name: "in to on fixes the task on the day it stands on, and the arrow keeps its days",
      plan: inThreeDays,
      mode: "on",
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 7, 2)], arrows: [arrow("A>B", "end-start", 3)] },
    },
    {
      name: "on to in says the days there are, so that the task stays where it is",
      plan: onLaterDay,
      mode: "in",
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 5)] },
    },
    {
      name: "on to in for a task that stands before the edge is in 0 d, which moves it to the edge",
      plan: onEarlierDay,
      mode: "in",
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 0)] },
    },
    {
      name: "on to linked makes the task follow, linked",
      plan: onLaterDay,
      mode: "linked",
      expected: linked,
    },
    {
      name: "the mode an arrow has already changes nothing",
      plan: inThreeDays,
      mode: "in",
      expected: inThreeDays,
    },
  ];

  it.each(cases)("$name", ({ plan, mode, expected }) => {
    const actual = setArrowMode(plan, "A>B", mode);

    expect(actual).toEqual(expected);
  });
});

describe("turnArrowMode", () => {
  const plan: TPlan = { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] };
  const cases: { name: string; directions: (1 | -1)[]; expected: TArrowMode[] }[] = [
    {
      name: "forward it goes from linked to in, to on, and to linked again",
      directions: [1, 1, 1],
      expected: ["in", "on", "linked"],
    },
    {
      name: "backward it goes from linked to on, to in, and to linked again",
      directions: [-1, -1, -1],
      expected: ["on", "in", "linked"],
    },
  ];

  it.each(cases)("$name", ({ directions, expected }) => {
    const actual: TArrowMode[] = [];
    let turned = plan;
    for (const direction of directions) {
      turned = turnArrowMode(turned, "A>B", direction);
      actual.push(getArrowMode(turned, turned.arrows[0]));
    }

    expect(actual).toEqual(expected);
  });

  it("a whole round moves nothing when the edges were together", () => {
    const expected = computeSchedule(plan.tasks, plan.arrows).dates;

    const turned = [1, 1, 1].reduce((turnedPlan) => turnArrowMode(turnedPlan, "A>B", 1), plan);
    const actual = computeSchedule(turned.tasks, turned.arrows).dates;

    expect(actual).toEqual(expected);
  });
});

describe("getLatestArrowId", () => {
  const cases: { name: string; plan: TPlan; expected: string | undefined }[] = [
    {
      name: "of a task that follows its arrows it is the arrow that decides its day",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 6), following("B", 2)],
        arrows: [arrow("A>B", "end-start", 1), arrow("X>B", "end-start", 0)],
      },
      expected: "X>B",
    },
    {
      name: "of a task that is fixed on its day it is the arrow that asks for the latest day",
      plan: {
        tasks: [fixed("A", 1, 3), fixed("X", 1, 6), fixed("B", 20, 2)],
        arrows: [arrow("A>B", "end-start", 9), arrow("X>B", "end-start", 0)],
      },
      expected: "A>B",
    },
    {
      name: "a task to which no arrow leads from the timeline has none",
      plan: { tasks: [fixed("B", 20, 2)], arrows: [arrow("A>B", "end-start", 9)] },
      expected: undefined,
    },
  ];

  it.each(cases)("$name", ({ plan, expected }) => {
    const actual = getLatestArrowId(plan.arrows, computeSchedule(plan.tasks, plan.arrows), "B");

    expect(actual).toEqual(expected);
  });
});

describe("changeArrow", () => {
  const plan: TPlan = { tasks: [fixed("A", 1, 3), fixed("B", 9, 2)], arrows: [arrow("A>B", "end-start", 1)] };
  const cases: { name: string; change: { kind?: TArrowKind; delay?: TArrowDelay }; expected: TPlan }[] = [
    {
      name: "a delay is set on the arrow and makes its next task follow its arrows",
      change: { delay: 4 },
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 4)] },
    },
    {
      name: "no days is a delay as any other",
      change: { delay: 0 },
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", 0)] },
    },
    {
      name: "linked is set as a delay is, and makes its next task follow its arrows",
      change: { delay: "linked" },
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start", "linked")] },
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
    { name: "removeTask", run: (given) => removeTask(given, "A") },
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
