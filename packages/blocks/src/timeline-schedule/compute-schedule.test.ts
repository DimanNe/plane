/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { computeSchedule, getConflictCause } from "./compute-schedule";
import { arrow, dates, day, fixed, following, PLAIN_SCHEDULE } from "./test-helpers";
import type { TSchedule, TScheduleArrow, TScheduleTask } from "./types";

type TCase = { name: string; tasks: TScheduleTask[]; arrows: TScheduleArrow[]; expected: TSchedule };

describe("computeSchedule", () => {
  const cases: TCase[] = [
    {
      name: "an end -> start arrow asks immediately for the day after the previous end",
      tasks: [fixed("A", 1, 3), following("B", 2)],
      arrows: [arrow("A>B", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], B: [4, 5] }),
        decidingArrowId: { B: "A>B" },
        gaps: { "A>B": 0 },
      },
    },
    {
      name: "an end -> start arrow with a delay asks for that many days later",
      tasks: [fixed("A", 1, 3), following("B", 2)],
      arrows: [arrow("A>B", "end-start", 2)],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], B: [6, 7] }),
        decidingArrowId: { B: "A>B" },
        gaps: { "A>B": 2 },
      },
    },
    {
      name: "a start -> start arrow asks immediately for the day of the previous start",
      tasks: [fixed("A", 1, 3), following("B", 2)],
      arrows: [arrow("A>B", "start-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], B: [1, 2] }),
        decidingArrowId: { B: "A>B" },
        gaps: { "A>B": 0 },
      },
    },
    {
      name: "a start -> start arrow with a delay asks for that many days after the previous start",
      tasks: [fixed("A", 1, 3), following("B", 2)],
      arrows: [arrow("A>B", "start-start", 2)],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], B: [3, 4] }),
        decidingArrowId: { B: "A>B" },
        gaps: { "A>B": 2 },
      },
    },
    {
      name: "an end -> end arrow asks immediately for an end on the day of the previous end",
      tasks: [fixed("A", 1, 3), following("B", 2)],
      arrows: [arrow("A>B", "end-end")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], B: [2, 3] }),
        decidingArrowId: { B: "A>B" },
        gaps: { "A>B": 0 },
      },
    },
    {
      name: "an end -> end arrow with a delay asks for an end that many days after the previous end",
      tasks: [fixed("A", 1, 3), following("B", 2)],
      arrows: [arrow("A>B", "end-end", 2)],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], B: [4, 5] }),
        decidingArrowId: { B: "A>B" },
        gaps: { "A>B": 2 },
      },
    },
    {
      name: "the day after the last day of a year is the first day of the next",
      tasks: [{ id: "A", duration: 2, start: { at: "2026-12-30" } }, following("B", 1)],
      arrows: [arrow("A>B", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: { A: { start: "2026-12-30", end: "2026-12-31" }, B: { start: "2027-01-01", end: "2027-01-01" } },
        decidingArrowId: { B: "A>B" },
        gaps: { "A>B": 0 },
      },
    },
    {
      name: "a task that follows several arrows starts on the latest day they ask for",
      tasks: [fixed("A", 1, 3), fixed("C", 1, 5), following("B", 2)],
      arrows: [arrow("A>B", "end-start"), arrow("C>B", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], C: [1, 5], B: [6, 7] }),
        decidingArrowId: { B: "C>B" },
        gaps: { "A>B": 2, "C>B": 0 },
        slack: { A: 2, C: 0, B: 0 },
        criticalTaskIds: ["C", "B"],
        criticalArrowIds: ["C>B"],
      },
    },
    {
      name: "of arrows that ask for the same day the first one decides, and each of them is critical",
      tasks: [fixed("A", 1, 3), fixed("C", 2, 2), following("B", 2)],
      arrows: [arrow("C>B", "end-start"), arrow("A>B", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], C: [2, 3], B: [4, 5] }),
        decidingArrowId: { B: "C>B" },
        gaps: { "C>B": 0, "A>B": 0 },
        slack: { A: 0, C: 0, B: 0 },
        criticalTaskIds: ["A", "C", "B"],
        criticalArrowIds: ["C>B", "A>B"],
      },
    },
    {
      name: "an arrow that asks a fixed task to start later than its day is a conflict",
      tasks: [fixed("A", 1, 3), fixed("B", 3, 2)],
      arrows: [arrow("A>B", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], B: [3, 4] }),
        gaps: { "A>B": -1 },
        conflicts: [
          {
            arrowId: "A>B",
            taskId: "B",
            fixedDay: day(3),
            askedDay: day(4),
            anchorDay: day(3),
            waysOut: [{ way: "follow-arrows" }, { way: "move-fixed-day", day: day(4) }, { way: "remove-arrow" }],
          },
        ],
      },
    },
    {
      name: "a shorter delay is a way out of a conflict when the arrow then asks for no more than the fixed day",
      tasks: [fixed("A", 1, 3), fixed("B", 5, 2)],
      arrows: [arrow("A>B", "end-start", 3)],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 3], B: [5, 6] }),
        gaps: { "A>B": 1 },
        conflicts: [
          {
            arrowId: "A>B",
            taskId: "B",
            fixedDay: day(5),
            askedDay: day(7),
            anchorDay: day(3),
            waysOut: [
              { way: "follow-arrows" },
              { way: "move-fixed-day", day: day(7) },
              { way: "shorten-delay", delay: 1 },
              { way: "remove-arrow" },
            ],
          },
        ],
      },
    },
    {
      name: "an arrow that asks a fixed task for the day it is fixed on is no conflict",
      tasks: [fixed("A", 1, 3), fixed("B", 4, 2)],
      arrows: [arrow("A>B", "end-start")],
      expected: { ...PLAIN_SCHEDULE, dates: dates({ A: [1, 3], B: [4, 5] }), gaps: { "A>B": 0 } },
    },
    {
      name: "a conflict of a start -> start arrow counts from the previous start",
      tasks: [fixed("A", 2, 3), fixed("B", 1, 2)],
      arrows: [arrow("A>B", "start-start", 1)],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [2, 4], B: [1, 2] }),
        gaps: { "A>B": -1 },
        conflicts: [
          {
            arrowId: "A>B",
            taskId: "B",
            fixedDay: day(1),
            askedDay: day(3),
            anchorDay: day(2),
            waysOut: [{ way: "follow-arrows" }, { way: "move-fixed-day", day: day(3) }, { way: "remove-arrow" }],
          },
        ],
      },
    },
    {
      name: "a conflict of an end -> end arrow gives the start that goes with the end it asks for",
      tasks: [fixed("A", 1, 5), fixed("B", 2, 2)],
      arrows: [arrow("A>B", "end-end")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 5], B: [2, 3] }),
        gaps: { "A>B": -2 },
        conflicts: [
          {
            arrowId: "A>B",
            taskId: "B",
            fixedDay: day(2),
            askedDay: day(4),
            anchorDay: day(5),
            waysOut: [{ way: "follow-arrows" }, { way: "move-fixed-day", day: day(4) }, { way: "remove-arrow" }],
          },
        ],
      },
    },
    {
      name: "an arrow whose other task is not on the timeline takes no part",
      tasks: [fixed("B", 3, 2)],
      arrows: [arrow("X>B", "end-start"), arrow("B>Y", "end-start")],
      expected: { ...PLAIN_SCHEDULE, dates: dates({ B: [3, 4] }) },
    },
    {
      name: "tasks connected two by two have no slack and nothing critical",
      tasks: [fixed("A", 1, 1), following("B", 1), fixed("C", 1, 1), following("D", 1)],
      arrows: [arrow("A>B", "end-start"), arrow("C>D", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 1], B: [2, 2], C: [1, 1], D: [2, 2] }),
        decidingArrowId: { B: "A>B", D: "C>D" },
        gaps: { "A>B": 0, "C>D": 0 },
      },
    },
    {
      name: "the chain that decides a group's last end is critical, and a task beside it can slip up to that end",
      tasks: [fixed("A", 1, 2), following("B", 5), following("C", 1)],
      arrows: [arrow("A>B", "end-start"), arrow("A>C", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 2], B: [3, 7], C: [3, 3] }),
        decidingArrowId: { B: "A>B", C: "A>C" },
        gaps: { "A>B": 0, "A>C": 0 },
        slack: { A: 0, B: 0, C: 4 },
        criticalTaskIds: ["A", "B"],
        criticalArrowIds: ["A>B"],
      },
    },
    {
      name: "slack is counted in each group from that group's own last end",
      tasks: [
        fixed("A", 1, 1),
        following("B", 1),
        following("C", 3),
        fixed("D", 10, 1),
        following("E", 1),
        following("F", 5),
      ],
      arrows: [
        arrow("A>B", "end-start"),
        arrow("A>C", "end-start"),
        arrow("D>E", "end-start"),
        arrow("D>F", "end-start"),
      ],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 1], B: [2, 2], C: [2, 4], D: [10, 10], E: [11, 11], F: [11, 15] }),
        decidingArrowId: { B: "A>B", C: "A>C", E: "D>E", F: "D>F" },
        gaps: { "A>B": 0, "A>C": 0, "D>E": 0, "D>F": 0 },
        slack: { A: 0, B: 2, C: 0, D: 0, E: 4, F: 0 },
        criticalTaskIds: ["A", "C", "D", "F"],
        criticalArrowIds: ["A>C", "D>F"],
      },
    },
    {
      name: "a task before a fixed task can slip until its arrow would become a conflict",
      tasks: [fixed("A", 1, 2), fixed("B", 6, 2), following("C", 1)],
      arrows: [arrow("A>B", "end-start"), arrow("B>C", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 2], B: [6, 7], C: [8, 8] }),
        decidingArrowId: { C: "B>C" },
        gaps: { "A>B": 3, "B>C": 0 },
        slack: { A: 3, B: 0, C: 0 },
        criticalTaskIds: ["B", "C"],
        criticalArrowIds: ["B>C"],
      },
    },
    {
      name: "a task whose arrow into a fixed task is a conflict already cannot slip",
      tasks: [fixed("A", 1, 5), fixed("B", 3, 2), following("C", 2)],
      arrows: [arrow("A>B", "end-start"), arrow("B>C", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 5], B: [3, 4], C: [5, 6] }),
        decidingArrowId: { C: "B>C" },
        gaps: { "A>B": -3, "B>C": 0 },
        conflicts: [
          {
            arrowId: "A>B",
            taskId: "B",
            fixedDay: day(3),
            askedDay: day(6),
            anchorDay: day(5),
            waysOut: [{ way: "follow-arrows" }, { way: "move-fixed-day", day: day(6) }, { way: "remove-arrow" }],
          },
        ],
        slack: { A: 0, B: 0, C: 0 },
        criticalTaskIds: ["A", "B", "C"],
        criticalArrowIds: ["B>C"],
      },
    },
    {
      name: "an arrow that asks a fixed task for exactly its day is critical when both its tasks are",
      tasks: [fixed("A", 1, 2), fixed("B", 3, 2), following("C", 1)],
      arrows: [arrow("A>B", "end-start"), arrow("B>C", "end-start")],
      expected: {
        ...PLAIN_SCHEDULE,
        dates: dates({ A: [1, 2], B: [3, 4], C: [5, 5] }),
        decidingArrowId: { C: "B>C" },
        gaps: { "A>B": 0, "B>C": 0 },
        slack: { A: 0, B: 0, C: 0 },
        criticalTaskIds: ["A", "B", "C"],
        criticalArrowIds: ["A>B", "B>C"],
      },
    },
  ];

  it.each(cases)("$name", ({ tasks, arrows, expected }) => {
    const actual = computeSchedule(tasks, arrows);

    expect(actual).toEqual(expected);
  });

  it("refuses arrows that form a loop, naming the tasks it cannot place", () => {
    const tasks = [fixed("A", 1, 1), following("B", 1), following("C", 1)];
    const arrows = [arrow("A>B", "end-start"), arrow("B>C", "end-start"), arrow("C>B", "end-start")];

    expect(() => computeSchedule(tasks, arrows)).toThrow(
      new Error("The arrows form a loop, so these tasks cannot be placed: B, C")
    );
  });

  it("refuses a task that follows its arrows when none leads to it from a task of the timeline", () => {
    const tasks = [following("B", 1)];
    const arrows = [arrow("X>B", "end-start")];

    expect(() => computeSchedule(tasks, arrows)).toThrow(
      new Error("Task B follows its arrows, but no arrow leads to it")
    );
  });
});

describe("getConflictCause", () => {
  it("names the fixed task and, back from the conflicting arrow, the arrows and tasks that decide where it asks", () => {
    const tasks = [fixed("A", 1, 2), fixed("E", 1, 1), following("B", 2), following("C", 1), fixed("D", 3, 1)];
    const arrows = [
      arrow("A>B", "end-start"),
      arrow("E>B", "end-start"),
      arrow("B>C", "end-start"),
      arrow("C>D", "end-start"),
    ];
    const schedule = computeSchedule(tasks, arrows);

    const actual = schedule.conflicts.map((conflict) => getConflictCause(arrows, schedule, conflict));

    expect(actual).toEqual([{ taskIds: ["D", "C", "B", "A"], arrowIds: ["C>D", "B>C", "A>B"] }]);
  });
});
