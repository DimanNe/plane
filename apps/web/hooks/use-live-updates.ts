/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
// store
import { LiveUpdates } from "@/store/live-updates";

/**
 * Follows what others change in the workspace for as long as one of its pages is open.
 */
export const useLiveUpdates = (workspaceSlug: string | undefined) => {
  useEffect(() => {
    if (!workspaceSlug) return;
    const liveUpdates = new LiveUpdates(workspaceSlug);
    return () => liveUpdates.stop();
  }, [workspaceSlug]);
};
