/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import type { IState, TStateGroups } from "@plane/types";
import { getStateOfKey, getStateOfShortcut, STATE_SHORTCUTS } from "./state-shortcut";

const state = (name: string, group: TStateGroups) => ({ id: name, name, group }) as IState;

/** The name of the state that each key means in a project with these states. */
const getStateNamesByKey = (states: IState[]) =>
  Object.fromEntries(
    STATE_SHORTCUTS.map((shortcut) => [shortcut.key, getStateOfShortcut(states, shortcut)?.name ?? null])
  );

describe("a key means the state of its name, else the first state of its group", () => {
  const cases: { name: string; states: IState[]; expected: Record<string, string | null> }[] = [
    {
      name: "the states of a new project: each key finds its name, and R finds nothing",
      states: [
        state("Backlog", "backlog"),
        state("Todo", "unstarted"),
        state("In Progress", "started"),
        state("Done", "completed"),
        state("Cancelled", "cancelled"),
      ],
      expected: { d: "Done", p: "In Progress", t: "Todo", r: null, c: "Cancelled" },
    },
    {
      name: "a state named Review answers to R, whatever its group",
      states: [state("Todo", "unstarted"), state("In Progress", "started"), state("Review", "started")],
      expected: { d: null, p: "In Progress", t: "Todo", r: "Review", c: null },
    },
    {
      name: "names are compared without regard to case; In Review and Canceled are taken too",
      states: [
        state("TODO", "unstarted"),
        state("in progress", "started"),
        state("In review", "started"),
        state("done", "completed"),
        state("Canceled", "cancelled"),
      ],
      expected: { d: "done", p: "in progress", t: "TODO", r: "In review", c: "Canceled" },
    },
    {
      name: "the name wins over a state that stands before it in the group",
      states: [
        state("Ready", "unstarted"),
        state("Todo", "unstarted"),
        state("Review", "started"),
        state("In Progress", "started"),
        state("Shipped", "completed"),
        state("Done", "completed"),
        state("Duplicate", "cancelled"),
        state("Cancelled", "cancelled"),
      ],
      expected: { d: "Done", p: "In Progress", t: "Todo", r: "Review", c: "Cancelled" },
    },
    {
      name: "a project that names its states otherwise: the first state of each group, and nothing for R",
      states: [
        state("Idea", "backlog"),
        state("Ready", "unstarted"),
        state("Next", "unstarted"),
        state("Doing", "started"),
        state("Testing", "started"),
        state("Shipped", "completed"),
        state("Dropped", "cancelled"),
      ],
      expected: { d: "Shipped", p: "Doing", t: "Ready", r: null, c: "Dropped" },
    },
    {
      name: "a group without a state: nothing for its key",
      states: [state("Backlog", "backlog"), state("Doing", "started")],
      expected: { d: null, p: "Doing", t: null, r: null, c: null },
    },
  ];

  it.each(cases)("$name", ({ states, expected }) => {
    expect(getStateNamesByKey(states)).toEqual(expected);
  });
});

/** The name of the state that each of `keys` means in a project with these states. */
const getStateNamesOfKeys = (states: IState[], keys: string[]) =>
  Object.fromEntries(keys.map((key) => [key, getStateOfKey(states, key)?.name ?? null]));

describe("every state answers to the first letter of its name; the letters of STATE_SHORTCUTS keep theirs", () => {
  const cases: { name: string; states: IState[]; keys: string[]; expected: Record<string, string | null> }[] = [
    {
      name: "the states of a new project: B means Backlog, and P and I both mean In Progress",
      states: [
        state("Backlog", "backlog"),
        state("Todo", "unstarted"),
        state("In Progress", "started"),
        state("Done", "completed"),
        state("Cancelled", "cancelled"),
      ],
      keys: ["b", "t", "p", "i", "d", "c", "r", "x"],
      expected: {
        b: "Backlog",
        t: "Todo",
        p: "In Progress",
        i: "In Progress",
        d: "Done",
        c: "Cancelled",
        r: null,
        x: null,
      },
    },
    {
      name: "a state the project added answers to its letter; one letter for two states means the first of them",
      states: [
        state("Backlog", "backlog"),
        state("Blocked", "backlog"),
        state("Todo", "unstarted"),
        state("Triage", "unstarted"),
        state("In Progress", "started"),
        state("Review", "started"),
        state("Done", "completed"),
        state("Cancelled", "cancelled"),
      ],
      keys: ["b", "t", "r", "i"],
      expected: { b: "Backlog", t: "Todo", r: "Review", i: "In Progress" },
    },
    {
      name: "a letter of STATE_SHORTCUTS keeps its group before the first letter, and only R, without a group, falls to it",
      states: [
        state("Idea", "backlog"),
        state("Ready", "unstarted"),
        state("Doing", "started"),
        state("Shipped", "completed"),
        state("Dropped", "cancelled"),
      ],
      keys: ["d", "p", "t", "c", "r", "s", "i"],
      expected: { d: "Shipped", p: "Doing", t: "Ready", c: "Dropped", r: "Ready", s: "Shipped", i: "Idea" },
    },
    {
      name: "the first letter is read without regard to case or leading spaces, and a digit answers too",
      states: [state(" waiting", "unstarted"), state("2nd look", "started")],
      keys: ["w", "2"],
      expected: { w: " waiting", "2": "2nd look" },
    },
  ];

  it.each(cases)("$name", ({ states, keys, expected }) => {
    expect(getStateNamesOfKeys(states, keys)).toEqual(expected);
  });
});
