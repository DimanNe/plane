/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState, useEffect } from "react";

const useDebounce = <T,>(value: T, milliSeconds: number): T => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    // Already the debounced value, as at every mount: a timer would set it again and change nothing, while what
    // waits for a page's timers to end (claude/checks/settle.py) would wait for it.
    // FOR_REVIEWER: debouncedValue is among the dependencies for the rule exhaustive-deps; its only change is the
    // timer's, after which this effect runs again and returns here. A value that comes back to the debounced one
    // while a timer is pending clears that timer and starts none; before, a new timer set the same value again,
    // which React ignores, so no caller saw a change either way.
    if (Object.is(value, debouncedValue)) return;
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, milliSeconds);

    return () => {
      clearTimeout(handler);
    };
  }, [value, milliSeconds, debouncedValue]);

  return debouncedValue;
};

export default useDebounce;
