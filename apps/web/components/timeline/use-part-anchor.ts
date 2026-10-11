/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useLayoutEffect, useRef } from "react";

// a text that is this near to where it has to be is there: places are computed, and never come out the same
const NO_DISTANCE = 0.1;

/**
 * The part of a text that the wheel turns at a place of the window: the one under it, or the nearest sideways for
 * a place beside the parts. Its place among the parts of the text.
 */
export const getNearestPartIndex = (text: Element, clientX: number) => {
  const distances = [...text.children].map((part) => {
    const { left, right } = part.getBoundingClientRect();
    return Math.max(left - clientX, clientX - right, 0);
  });
  return distances.indexOf(Math.min(...distances));
};

/**
 * A notch of the wheel on a part of a text changes what the text says, and with it how wide its parts are: "in"
 * becomes "linked", a date takes the place of a number of days. The part under the pointer could come to lie
 * beside it, and the next notch would turn another part. So the turned part is kept under the pointer: `hold`
 * is called before a notch changes the text, with the part and the pointer, and after every change `onShift` gets
 * the distance by which the text has to move right for the pointer to be as far into the part as it was, until
 * the pointer moves. A pointer beside the part keeps the edge of the part it is at.
 *
 * `getPart` gives the part only while the text takes a shift: a text that stood still under the shifts it is
 * asked for would be asked without end.
 */
export const usePartAnchor = (getPart: () => Element | undefined, onShift: (distance: number) => void) => {
  // where the pointer is, no further than the part reaches, and how far into the part: 0 at its left edge, 1 at
  // its right one
  const anchorRef = useRef<{ x: number; share: number }>(undefined);

  useLayoutEffect(() => {
    const anchor = anchorRef.current;
    const part = anchor && getPart();
    if (!part) return;
    const { left, width } = part.getBoundingClientRect();
    const distance = anchor.x - anchor.share * width - left;
    if (Math.abs(distance) > NO_DISTANCE) onShift(distance);
  });

  return {
    hold: (part: Element, clientX: number) => {
      const { left, right, width } = part.getBoundingClientRect();
      const x = Math.min(Math.max(clientX, left), right);
      anchorRef.current = { x, share: width ? (x - left) / width : 0 };
    },
    // the pointer has moved: the text stays where it is now
    release: () => {
      anchorRef.current = undefined;
    },
  };
};
