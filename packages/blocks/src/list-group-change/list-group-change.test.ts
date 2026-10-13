/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import type { TGroupedIssues } from "@plane/types";
import { getLinesGoneToAnotherGroup } from "./list-group-change";
import type { TLineGroupChange } from "./list-group-change";

describe("a line goes to another group when its work item leaves exactly one group and enters exactly one", () => {
  const cases: { name: string; before: TGroupedIssues; after: TGroupedIssues; expected: TLineGroupChange[] }[] = [
    {
      name: "a state is changed: the line goes from the group of the old state to that of the new one",
      before: { todo: ["one", "two"], done: ["three"] },
      after: { todo: ["two"], done: ["three", "one"] },
      expected: [{ issueId: "one", groupId: "todo", newGroupId: "done" }],
    },
    {
      name: "several work items are changed together: each line goes its own way",
      before: { todo: ["one", "two"], started: ["three"], done: [] },
      after: { todo: [], started: ["one"], done: ["two", "three"] },
      expected: [
        { issueId: "one", groupId: "todo", newGroupId: "started" },
        { issueId: "two", groupId: "todo", newGroupId: "done" },
        { issueId: "three", groupId: "started", newGroupId: "done" },
      ],
    },
    {
      name: "the new group had no work item, and the list had not kept it",
      before: { todo: ["one"] },
      after: { todo: [], done: ["one"] },
      expected: [{ issueId: "one", groupId: "todo", newGroupId: "done" }],
    },
    {
      name: "a line that takes another place in its own group goes nowhere",
      before: { todo: ["one", "two", "three"] },
      after: { todo: ["three", "one", "two"] },
      expected: [],
    },
    {
      name: "a new work item and a deleted one have no line that went anywhere",
      before: { todo: ["one"], done: ["two"] },
      after: { todo: ["one", "three"], done: [] },
      expected: [],
    },
    {
      name: "one label is replaced by another: the line of that label goes, the line of the label kept stays",
      before: { bug: ["one"], urgent: ["one", "two"], later: [] },
      after: { bug: ["one"], urgent: ["two"], later: ["one"] },
      expected: [{ issueId: "one", groupId: "urgent", newGroupId: "later" }],
    },
    {
      name: "a label more is a line more, a label less is a line less: no line went anywhere",
      before: { bug: ["one", "two"], urgent: ["two"], later: [] },
      after: { bug: ["one", "two"], urgent: [], later: ["one"] },
      expected: [],
    },
    {
      name: "two labels are replaced at once: the groups do not tell which line went where",
      before: { bug: ["one"], urgent: ["one"], later: [], idea: [] },
      after: { bug: [], urgent: [], later: ["one"], idea: ["one"] },
      expected: [],
    },
  ];

  it.each(cases)("$name", ({ before, after, expected }) => {
    expect(getLinesGoneToAnotherGroup(before, after)).toEqual(expected);
  });
});
