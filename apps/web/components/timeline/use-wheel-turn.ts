/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useRef } from "react";
// plane imports
import type { TPlan } from "@plane/blocks/timeline-schedule";
import { useLatestCallback } from "@plane/hooks";
// local imports
import type { TTimelineOperation } from "./operation";

// how long the wheel rests before what it changed is saved
const WHEEL_REST_TIME = 800;

export type TWheelTurn = ReturnType<typeof useWheelTurn>;

/**
 * The wheel on a value of the plan turns that value, a step a notch: the days of a delay, a date beside a bar.
 * Many notches are one change to the person who turns the wheel, so they are one operation: begun at the first
 * notch, shown at every notch, and saved when the wheel has rested for a moment, when what it turned says that
 * the pointer has left it, or when a button is pressed. Escape drops it. It never stays open: changes of the
 * plan made elsewhere wait for its end.
 *
 * The timeline has one of these for everything the wheel turns, so that a turn of one value ends before a turn
 * of another begins.
 */
export const useWheelTurn = (operation: TTimelineOperation) => {
  // the operation that is going on: what is turned, the plan it began with, and the timer of the rest
  const turnRef = useRef<{ key: string; plan: TPlan; timer: number }>(undefined);

  const end = useLatestCallback((isAborted: boolean) => {
    const turn = turnRef.current;
    if (!turn) return;
    turnRef.current = undefined;
    window.clearTimeout(turn.timer);
    document.removeEventListener("keydown", handleKeyDown, true);
    document.removeEventListener("pointerdown", handlePress, true);
    if (isAborted) operation.abort();
    else operation.commit();
  });

  const handleKeyDown = useLatestCallback((event: KeyboardEvent) => {
    if (event.key !== "Escape") return;
    // Escape ends the operation and nothing else
    event.stopPropagation();
    event.preventDefault();
    end(true);
  });

  // a press begins another gesture, whose operation would take the place of this one
  const handlePress = useLatestCallback(() => end(false));

  /** A notch on the value named by `key`: `change` gives the plan after it, from the plan the turn began with. */
  const turn = useLatestCallback((key: string, change: (plan: TPlan) => TPlan) => {
    if (turnRef.current && turnRef.current.key !== key) end(false);
    if (!turnRef.current) {
      const plan = operation.begin();
      if (!plan) return;
      turnRef.current = { key, plan, timer: 0 };
      document.addEventListener("keydown", handleKeyDown, true);
      document.addEventListener("pointerdown", handlePress, true);
    }
    window.clearTimeout(turnRef.current.timer);
    turnRef.current.timer = window.setTimeout(() => end(false), WHEEL_REST_TIME);
    operation.preview(change(turnRef.current.plan));
  });

  useEffect(() => () => end(true), [end]);

  return useMemo(() => ({ turn, end, getTurnedKey: () => turnRef.current?.key }), [turn, end]);
};
