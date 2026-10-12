/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IState, TStateGroups } from "@plane/types";

export type TStateShortcut = {
  id: "done" | "in_progress" | "todo" | "review" | "cancelled";
  /** The key pressed after S. */
  key: string;
  /** What a project may call the state, the usual name first. */
  names: string[];
  /** Review has none: the groups of a project are fixed, and no group means "in review". */
  group?: TStateGroups;
};

/**
 * The states that have keys of their own. Every project names its states itself, so a key cannot stand for one
 * state of the app: it stands for a name, and for a group where a project has no state of that name.
 */
export const STATE_SHORTCUTS: TStateShortcut[] = [
  { id: "done", key: "d", names: ["Done"], group: "completed" },
  { id: "in_progress", key: "p", names: ["In Progress"], group: "started" },
  { id: "todo", key: "t", names: ["Todo"], group: "unstarted" },
  { id: "review", key: "r", names: ["Review", "In Review"] },
  { id: "cancelled", key: "c", names: ["Cancelled", "Canceled"], group: "cancelled" },
];

/**
 * The state of a project that the shortcut means: the one of that name, else the first of the shortcut's group.
 * `states` are in the order in which the project lists them.
 */
export const getStateOfShortcut = (states: IState[], shortcut: TStateShortcut): IState | undefined =>
  states.find((state) => shortcut.names.some((name) => name.toLowerCase() === state.name.toLowerCase())) ??
  states.find((state) => state.group === shortcut.group);
