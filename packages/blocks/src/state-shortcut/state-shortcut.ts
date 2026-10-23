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
 * The states whose keys were settled before every state had the first letter of its name (see getStateOfKey). Every
 * project names its states itself, so such a key cannot stand for one state of the app: it stands for a name, and
 * for a group where a project has no state of that name.
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

/**
 * The state of a project that the key pressed after S means. Every state answers to the first letter of its name,
 * whatever the project calls it; the letters of STATE_SHORTCUTS keep the meaning they had before, so P still means
 * In Progress, and only where one of them finds nothing does it mean the first state of that letter. Where several
 * states begin with the same letter, the key means the first of them. `states` are in the order in which the project
 * lists them; `key` is lower case.
 */
export const getStateOfKey = (states: IState[], key: string): IState | undefined => {
  // FOR_REVIEWER: two states with one first letter, as Todo and Triage in PLANE, or Backlog and Blocked: the key
  // means the first of them, here Todo (the letter of STATE_SHORTCUTS) or the one listed first, and the other is
  // reached through the menu that S opens. Alternatives: the same key again on a work item already in one of them
  // goes on to the next (which would make S D on a line of Done, at the end of a group worked down, move it), or a
  // second letter after the first narrows them down.
  const shortcut = STATE_SHORTCUTS.find((stateShortcut) => stateShortcut.key === key);
  return (
    (shortcut && getStateOfShortcut(states, shortcut)) ??
    states.find((state) => state.name.trim().charAt(0).toLowerCase() === key)
  );
};
