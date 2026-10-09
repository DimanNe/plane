/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useInsertionEffect, useRef } from "react";

/**
 * Returns a function that calls the callback of the latest render, for a listener that is
 * registered once and must still act on the current state.
 *
 * It stands in for React's `useEffectEvent`. The React version in use refreshes an Effect Event
 * only in a plain function component: inside a `memo` or `forwardRef` component it keeps calling
 * the callback of the first render. Every MobX `observer` component is a `memo` component, so a
 * panel that checks "am I open?" in its outside-click callback would never close.
 */
export const useLatestCallback = <TArgs extends unknown[], TReturn>(
  callback: (...args: TArgs) => TReturn
): ((...args: TArgs) => TReturn) => {
  const latestCallback = useRef(callback);

  useInsertionEffect(() => {
    latestCallback.current = callback;
  });

  return useCallback((...args: TArgs) => latestCallback.current(...args), []);
};
