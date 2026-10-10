/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import type { TTimelineChanges, TTimelineDependency, TTimelineDependencyTypes } from "@plane/types";
import { addArrow, changeArrow, moveTask, placeTask, removeArrow } from "./gestures";
import { getChanges, getPlan } from "./stored-plan";
import type { TStoredTask } from "./stored-plan";
import { arrow, day, fixed, following } from "./test-helpers";
import type { TPlan } from "./types";

/** A stored work item with its dates as days of January 2026; `null` for a date it does not have. */
const issue = (id: string, start: number | null, target: number | null, is_start_fixed = true): TStoredTask => ({
  id,
  start_date: start === null ? null : day(start),
  target_date: target === null ? null : day(target),
  is_start_fixed,
});

/** A stored dependency named by its work items, "A>B" from the predecessor A; the name is its id. */
const dependency = (name: string, relation_type: TTimelineDependencyTypes, delay = 0): TTimelineDependency => {
  const [predecessor_id, dependent_id] = name.split(">");
  return { id: name, predecessor_id, dependent_id, relation_type, delay };
};

describe("getPlan", () => {
  const cases: { name: string; issues: TStoredTask[]; dependencies: TTimelineDependency[]; expected: TPlan }[] = [
    {
      name: "a work item with both dates is a task that lasts from its start date to its due date, both counted",
      issues: [issue("A", 1, 3), issue("B", 5, 5)],
      dependencies: [],
      expected: { tasks: [fixed("A", 1, 3), fixed("B", 5, 1)], arrows: [] },
    },
    {
      name: "a work item without both dates or with a start after its due date is not on the timeline",
      issues: [issue("A", 1, null), issue("B", null, 3), issue("C", null, null), issue("D", 4, 3)],
      dependencies: [],
      expected: { tasks: [], arrows: [] },
    },
    {
      name: "blocking is an end -> start arrow, start_before start -> start and finish_before end -> end",
      issues: [],
      dependencies: [
        dependency("A>B", "blocking", 1),
        dependency("A>C", "start_before", 2),
        dependency("A>D", "finish_before", 3),
      ],
      expected: {
        tasks: [],
        arrows: [arrow("A>B", "end-start", 1), arrow("A>C", "start-start", 2), arrow("A>D", "end-end", 3)],
      },
    },
    {
      name: "a work item whose start is not fixed follows its arrows when one leads to it from a task",
      issues: [issue("A", 1, 3), issue("B", 8, 9, false)],
      dependencies: [dependency("A>B", "blocking")],
      expected: { tasks: [fixed("A", 1, 3), following("B", 2)], arrows: [arrow("A>B", "end-start")] },
    },
    {
      name: "a work item whose start is not fixed is fixed on its start date when no arrow leads to it from a task",
      issues: [issue("A", null, null), issue("B", 8, 9, false), issue("C", 1, 1, false)],
      dependencies: [dependency("A>B", "blocking")],
      expected: { tasks: [fixed("B", 8, 2), fixed("C", 1, 1)], arrows: [arrow("A>B", "end-start")] },
    },
  ];

  it.each(cases)("$name", ({ issues, dependencies, expected }) => {
    const actual = getPlan(issues, dependencies);

    expect(actual).toEqual(expected);
  });
});

describe("getChanges", () => {
  const issues = [issue("A", 1, 3), issue("B", 4, 5, false), issue("C", 1, 2), issue("D", null, null)];
  const dependencies = [dependency("A>B", "blocking"), dependency("D>C", "blocking")];
  const plan = getPlan(issues, dependencies);
  const nothing: TTimelineChanges = { dependencies: [], removed_dependencies: [], issues: [] };
  const cases: { name: string; stored?: TStoredTask[]; changed: TPlan; expected: TTimelineChanges }[] = [
    {
      name: "a plan that says what is stored changes nothing",
      changed: plan,
      expected: nothing,
    },
    {
      name: "a stored date that differs from the computed one is saved as computed",
      stored: [issue("A", 1, 3), issue("B", 8, 9, false), issue("C", 1, 2), issue("D", null, null)],
      changed: plan,
      expected: {
        ...nothing,
        issues: [{ id: "B", start_date: day(4), target_date: day(5), is_start_fixed: false }],
      },
    },
    {
      name: "a work item stored as following its arrows that the plan holds fixed is saved as fixed",
      stored: [issue("A", 1, 3), issue("B", 4, 5, false), issue("C", 1, 2, false), issue("D", null, null)],
      changed: plan,
      expected: {
        ...nothing,
        issues: [{ id: "C", start_date: day(1), target_date: day(2), is_start_fixed: true }],
      },
    },
    {
      name: "a moved task is saved with every task that moved with it",
      changed: moveTask(plan, "A", day(3)),
      expected: {
        ...nothing,
        issues: [
          { id: "A", start_date: day(3), target_date: day(5), is_start_fixed: true },
          { id: "B", start_date: day(6), target_date: day(7), is_start_fixed: false },
        ],
      },
    },
    {
      name: "a changed delay is saved as the dependency with its new delay",
      changed: changeArrow(plan, "A>B", { delay: 2 }),
      expected: {
        ...nothing,
        dependencies: [{ predecessor_id: "A", dependent_id: "B", relation_type: "blocking", delay: 2 }],
        issues: [{ id: "B", start_date: day(6), target_date: day(7), is_start_fixed: false }],
      },
    },
    {
      name: "a changed kind is saved by removing the dependency and giving the new one",
      changed: changeArrow(plan, "A>B", { kind: "end-end" }),
      expected: {
        dependencies: [{ predecessor_id: "A", dependent_id: "B", relation_type: "finish_before", delay: 0 }],
        removed_dependencies: ["A>B"],
        issues: [{ id: "B", start_date: day(2), target_date: day(3), is_start_fixed: false }],
      },
    },
    {
      name: "a new arrow is saved with the relation type of its kind, and its next task as following its arrows",
      changed: addArrow(plan, "A", "C", "start-start") as TPlan,
      expected: {
        ...nothing,
        dependencies: [{ predecessor_id: "A", dependent_id: "C", relation_type: "start_before", delay: 0 }],
        issues: [{ id: "C", start_date: day(1), target_date: day(2), is_start_fixed: false }],
      },
    },
    {
      name: "a removed arrow is removed, and its task saved as fixed where it stood",
      changed: removeArrow(plan, "A>B"),
      expected: {
        ...nothing,
        removed_dependencies: ["A>B"],
        issues: [{ id: "B", start_date: day(4), target_date: day(5), is_start_fixed: true }],
      },
    },
    {
      name: "a work item put on the timeline is saved with its dates, and its arrows take part from then on",
      changed: placeTask(plan, "D", day(2)),
      expected: {
        ...nothing,
        issues: [{ id: "D", start_date: day(2), target_date: day(2), is_start_fixed: true }],
      },
    },
  ];

  it.each(cases)("$name", ({ stored, changed, expected }) => {
    const actual = getChanges(stored ?? issues, dependencies, changed);

    expect(actual).toEqual(expected);
  });
});
