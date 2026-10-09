/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { FC } from "react";
// plane imports
import { CircularProgress } from "@makeplane/propel/components/circular-progress";
import { MilestoneDone, MilestoneInProgress, MilestoneNotStarted } from "@makeplane/propel/icons";
import type { ISvgIcons } from "@plane/blocks/icons";
import { useTranslation } from "@plane/i18n";
import type { TMilestone } from "@plane/types";
// helpers
import { getMilestoneProgress, getMilestoneState } from "@/helpers/milestone.helper";
import type { TMilestoneState } from "@/helpers/milestone.helper";

const MILESTONE_STATE_ICONS: Record<TMilestoneState, FC<ISvgIcons>> = {
  not_started: MilestoneNotStarted,
  in_progress: MilestoneInProgress,
  done: MilestoneDone,
};

type Props = {
  milestone: TMilestone;
};

export function MilestoneStateIcon(props: Props & { className?: string }) {
  const { milestone, className } = props;
  const Icon = MILESTONE_STATE_ICONS[getMilestoneState(milestone)];

  return <Icon className={className} />;
}

export function MilestoneProgress(props: Props & { label?: string }) {
  const { milestone, label } = props;
  // translation
  const { t } = useTranslation();
  // derived values
  const progress = getMilestoneProgress(milestone);

  return (
    <div className="flex flex-shrink-0 items-center gap-2 text-body-xs-regular text-secondary">
      <CircularProgress value={progress} size="md" variant="success" aria-label={t("common.progress")} />
      <span>
        {progress}% {label}
      </span>
    </div>
  );
}
