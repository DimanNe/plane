/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
// plane imports
import { useLatestCallback } from "@plane/hooks";

/**
 * What the pointer is over, known a moment late. What shows more under the pointer should not flash while the
 * pointer only crosses it, and should stay while the pointer crosses the gap to what it showed: so the pointer
 * has to stay for `enterDelay`, and what it has left is forgotten after `leaveDelay`, unless it is over something
 * again by then.
 */
export const useDelayedHover = <T>(enterDelay: number, leaveDelay: number) => {
  const timerRef = useRef<number>(undefined);
  const [hovered, setHovered] = useState<T>();

  const handleHover = useLatestCallback((value: T | undefined) => {
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setHovered(value), value === undefined ? leaveDelay : enterDelay);
  });
  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  return [hovered, handleHover, setHovered] as const;
};
