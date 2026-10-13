/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * What an arrow is doing at this moment, which its line and its text show at a glance:
 * - "rest": nothing;
 * - "hovered": the pointer is on its line or on its text;
 * - "selected": its control is open;
 * - "changing": the operation that is going on has changed what it asks or how long it is;
 * - "stopping": it is the reason why the bar that is dragged does not go further.
 * What the plan says of the arrow, that it is critical or in conflict, is another thing: that is its colour at
 * rest.
 */
export type TArrowState = "rest" | "hovered" | "selected" | "changing" | "stopping";

export type TArrowStates = {
  hoveredArrowId: string | undefined;
  selectedArrowId: string | undefined;
  changingArrowIds: string[];
  stoppingArrowIds: string[];
};

/** The one place that says which state an arrow is in: of those that hold, the one that matters most now. */
export const getArrowState = (arrowId: string, states: TArrowStates): TArrowState => {
  if (states.stoppingArrowIds.includes(arrowId)) return "stopping";
  if (states.selectedArrowId === arrowId) return "selected";
  if (states.changingArrowIds.includes(arrowId)) return "changing";
  return states.hoveredArrowId === arrowId ? "hovered" : "rest";
};

/**
 * The state that an arrow shows when the plan does not keep it: that it is red tells more than that the
 * operation changes it, and less than that it stops the move.
 */
export const getShownArrowState = (state: TArrowState, isInConflict: boolean): TArrowState =>
  isInConflict && state === "changing" ? "rest" : state;

/**
 * How a state looks on the line of an arrow: how strong the line is, and for a state of the move the colour that
 * takes the place of the arrow's own. Changing is green and stopping is amber: neither is the red of a conflict,
 * nor the blue of a selected arrow and of the critical arrows around them.
 */
export const ARROW_LINE_LOOKS: Record<TArrowState, { strokeWidth: number; colour?: "changing" | "stopping" }> = {
  rest: { strokeWidth: 1.5 },
  hovered: { strokeWidth: 2.5 },
  selected: { strokeWidth: 3 },
  changing: { strokeWidth: 3, colour: "changing" },
  stopping: { strokeWidth: 3.5, colour: "stopping" },
};

/** How a state looks on the text of an arrow. A state of the move is stronger than the pointer on a part. */
export const ARROW_TEXT_CLASS_NAMES: Record<TArrowState, string> = {
  rest: "",
  hovered: "border-accent-strong",
  selected: "border-accent-strong bg-accent-subtle",
  changing: "border-success-strong! bg-success-subtle text-success-primary",
  stopping: "border-warning-strong! bg-warning-subtle text-warning-primary",
};
