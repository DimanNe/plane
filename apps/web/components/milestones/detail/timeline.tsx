/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
import { observer } from "mobx-react";
// plane imports
import { setToast } from "@plane/blocks/toast";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { IBlockUpdateData, IBlockUpdateDependencyData, TIssue } from "@plane/types";
import { EIssuesStoreType, GANTT_TIMELINE_TYPE } from "@plane/types";
import { getDate } from "@plane/utils";
// components
import { TimeLineTypeContext } from "@/components/gantt-chart/contexts";
import { GanttChartRoot } from "@/components/gantt-chart/root";
import { IssueGanttSidebar } from "@/components/gantt-chart/sidebar/issues/sidebar";
import { IssueGanttBlock } from "@/components/issues/issue-layouts/gantt/blocks";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
import { useMilestone } from "@/hooks/store/use-milestone";
import { useUserPermissions } from "@/hooks/store/user";
import { useIssuesActions } from "@/hooks/use-issues-actions";

type Props = {
  workspaceSlug: string;
  projectId: string;
  milestoneId: string;
};

export const MilestoneWorkItemsTimeline = observer(function MilestoneWorkItemsTimeline(props: Props) {
  const { workspaceSlug, projectId, milestoneId } = props;
  // store hooks
  const { getMilestoneById, getMilestoneWorkItemIds } = useMilestone();
  const { issues } = useIssues(EIssuesStoreType.PROJECT);
  const { updateIssue } = useIssuesActions(EIssuesStoreType.PROJECT);
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

  const updateBlockStructure = (issue: TIssue, { start_date, target_date }: IBlockUpdateData) =>
    updateIssue?.(issue.project_id, issue.id, { start_date, target_date });

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
    <TimeLineTypeContext.Provider value={GANTT_TIMELINE_TYPE.ISSUE}>
      <div className="h-full w-full">
        <GanttChartRoot
          border={false}
          title={t("issue.label", { count: 2 })}
          loaderTitle={t("issue.label", { count: 2 })}
          blockIds={workItemIds}
          initialDate={getDate(milestone?.target_date)}
          blockUpdateHandler={updateBlockStructure}
          blockToRender={(data: TIssue) => <IssueGanttBlock issueId={data.id} />}
          sidebarToRender={(sidebarProps) => <IssueGanttSidebar {...sidebarProps} showAllBlocks />}
          enableBlockLeftResize={isEditingAllowed}
          enableBlockRightResize={isEditingAllowed}
          enableBlockMove={isEditingAllowed}
          enableAddBlock={isEditingAllowed}
          updateBlockDates={updateBlockDates}
          showAllBlocks
          enableDependency
        />
      </div>
    </TimeLineTypeContext.Provider>
  );
});
