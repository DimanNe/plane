/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { WarningTriangleOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import { renderFormattedDate } from "@plane/utils";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";

type Props = {
  milestoneId: string | null | undefined;
  dueDate: string | null;
};

/** Warns that a work item ends after the target date of its milestone. */
export const MilestoneDueDateWarning = observer(function MilestoneDueDateWarning(props: Props) {
  const { milestoneId, dueDate } = props;
  // store hooks
  const { getMilestoneById } = useMilestone();
  // translation
  const { t } = useTranslation();
  // derived values
  const milestone = milestoneId ? getMilestoneById(milestoneId) : null;

  if (!milestone?.target_date || !dueDate || dueDate <= milestone.target_date) return null;

  return (
    <Tooltip
      label={t("project_milestones.due_date_after_target_date", {
        title: milestone.title,
        date: renderFormattedDate(milestone.target_date),
      })}
    >
      <WarningTriangleOutline className="size-4 flex-shrink-0 text-warning-primary" />
    </Tooltip>
  );
});
