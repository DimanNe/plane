/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { setToast } from "@plane/blocks/toast";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { IBlockUpdateDependencyData } from "@plane/types";
import { EIssuesStoreType } from "@plane/types";
// components
import { WorkItemsTimeline } from "@/components/timeline/root";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
import { useMilestone } from "@/hooks/store/use-milestone";
import { useUserPermissions } from "@/hooks/store/user";

type Props = {
  workspaceSlug: string;
  projectId: string;
  milestoneId: string;
};

export const MilestoneWorkItemsTimeline = observer(function MilestoneWorkItemsTimeline(props: Props) {
  const { workspaceSlug, projectId, milestoneId } = props;
  // states
  const [showOnlyLeaves, setShowOnlyLeaves] = useState(false);
  // store hooks
  const { getMilestoneById, getMilestoneWorkItemIds } = useMilestone();
  const { issues } = useIssues(EIssuesStoreType.PROJECT);
  const { allowPermissions } = useUserPermissions();
  // translation
  const { t } = useTranslation();
  // derived values
  const milestone = getMilestoneById(milestoneId);
  const workItemIds = getMilestoneWorkItemIds(milestoneId);
  const isEditingAllowed = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT
  );

  const updateBlockDates = useCallback(
    (updates: IBlockUpdateDependencyData[]) =>
      issues.updateIssueDates(workspaceSlug, updates, projectId).catch(() => {
        setToast({
          type: "error",
          title: t("toast.error"),
          message: t("project_milestones.toast.dates_update_failed"),
        });
      }),
    [issues, projectId, workspaceSlug, t]
  );

  return (
    <div className="h-full w-full">
      <WorkItemsTimeline
        workItemIds={workItemIds}
        focusDate={milestone?.target_date}
        isEditable={isEditingAllowed}
        showOnlyLeaves={showOnlyLeaves}
        onShowOnlyLeavesChange={setShowOnlyLeaves}
        updateDates={updateBlockDates}
      />
    </div>
  );
});
