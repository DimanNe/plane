/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
// plane imports
import { useLatestCallback } from "@plane/hooks";

// A wheel that sends its movement in small pieces, as a touchpad does, makes a notch of this many pixels. One
// notch of a mouse wheel is more than this, and counts as one.
const WHEEL_NOTCH = 50;
// the height of a line for a wheel that reports lines
export const WHEEL_LINE_HEIGHT = 16;

/**
 * The wheel over an element changes a number there: `onNotch` gets 1 for a notch up and -1 for a notch down. The
 * wheel then does nothing else over that element: it does not zoom the timeline, scroll, or change a focused
 * number field by itself. Without `onNotch` the wheel does there what it does anywhere.
 */
export const useWheelNotches = (element: HTMLElement | null, onNotch: ((direction: 1 | -1) => void) | undefined) => {
  const handleNotch = useLatestCallback((direction: 1 | -1) => onNotch?.(direction));
  const isListening = !!onNotch;

  useEffect(() => {
    if (!element || !isListening) return;
    let moved = 0;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      moved += event.deltaY * (event.deltaMode === WheelEvent.DOM_DELTA_LINE ? WHEEL_LINE_HEIGHT : 1);
      if (Math.abs(moved) < WHEEL_NOTCH) return;
      handleNotch(moved < 0 ? 1 : -1);
      moved = 0;
    };
    // the wheel is cancelled, which a listener that React adds cannot do
    element.addEventListener("wheel", handleWheel, { passive: false });
    return () => element.removeEventListener("wheel", handleWheel);
  }, [element, isListening, handleNotch]);
};
