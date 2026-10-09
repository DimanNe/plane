/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Check, CloudOff, Dot } from "lucide-react";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { Badge } from "@makeplane/propel/components/badge";

type Props = {
  syncStatus: "syncing" | "synced" | "unsaved" | "error";
};

const BADGE_CONTENT = {
  syncing: {
    label: "Syncing...",
    tooltipLabel: "Syncing... Your changes are being synced with the server. You can continue making changes.",
  },
  synced: {
    label: "Saved",
    tooltipLabel: "Saved. The server has stored all your changes.",
  },
  unsaved: {
    label: "Unsaved changes",
    tooltipLabel: "Unsaved changes. The server has not stored your latest changes yet. Keep this page open.",
  },
  error: {
    label: "Connection lost",
    tooltipLabel:
      "Connection lost. We're having trouble connecting to the websocket server. Your changes will be synced and saved every 10 seconds.",
  },
};

const BADGE_VARIANT = { syncing: "brand", synced: "neutral", unsaved: "warning", error: "danger" } as const;

const BADGE_ICON = { syncing: Dot, synced: Check, unsaved: Dot, error: CloudOff };

export function PageSyncingBadge({ syncStatus }: Props) {
  const content = BADGE_CONTENT[syncStatus];
  const Icon = BADGE_ICON[syncStatus];

  return (
    <Tooltip label={content.tooltipLabel} layout="stacked">
      <span className="animate-quickFadeIn">
        <Badge
          variant={BADGE_VARIANT[syncStatus]}
          size="sm"
          startIcon={<Icon className="size-4" />}
          label={content.label}
        />
      </span>
    </Tooltip>
  );
}
