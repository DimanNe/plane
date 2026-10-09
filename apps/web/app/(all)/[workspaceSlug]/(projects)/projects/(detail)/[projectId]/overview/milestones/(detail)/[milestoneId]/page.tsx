/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { EmptyStateDetailed } from "@plane/blocks/empty-state";
import { PROJECT_MILESTONE_WORK_ITEMS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// components
import { PageHead } from "@/components/core/page-title";
import { IssuePeekOverview } from "@/components/issues/peek-overview";
import { MilestoneWorkItemsTimeline } from "@/components/milestones/detail/timeline";
import { GanttLayoutLoader } from "@/components/ui/loader/layouts/gantt-layout-loader";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
import type { Route } from "./+types/page";

function MilestoneDetailPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId, milestoneId } = params;
  // router
  const router = useAppRouter();
  // store hooks
  const { fetchedMap, getMilestoneById, fetchMilestoneWorkItems } = useMilestone();
  const { getProjectById } = useProject();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  // translation
  const { t } = useTranslation();
  // derived values
  const project = getProjectById(projectId);
  const milestone = getMilestoneById(milestoneId);
  const currentProjectRole = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId);
  const pageTitle = project?.name && milestone?.title ? `${project.name} - ${milestone.title}` : undefined;

  const { isLoading } = useSWR(
    PROJECT_MILESTONE_WORK_ITEMS(milestoneId, currentProjectRole),
    () => fetchMilestoneWorkItems(workspaceSlug, projectId, milestoneId),
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  if (!fetchedMap[projectId] || isLoading) return <GanttLayoutLoader />;

  if (!milestone)
    return (
      <div className="h-full place-items-center">
        <EmptyStateDetailed
          assetKey="milestone"
          title={t("project_milestones.not_found.title")}
          description={t("project_milestones.not_found.description")}
          actions={[
            {
              label: t("project_milestones.not_found.view_milestones"),
              onClick: () => router.push(`/${workspaceSlug}/projects/${projectId}/overview`),
              variant: "primary",
            },
          ]}
        />
      </div>
    );

  return (
    <>
      <PageHead title={pageTitle} />
      <div className="h-full w-full overflow-hidden">
        {/* the timeline opens at the target date of the milestone it is mounted with */}
        <MilestoneWorkItemsTimeline
          key={milestoneId}
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          milestoneId={milestoneId}
        />
      </div>
      <IssuePeekOverview />
    </>
  );
}

export default observer(MilestoneDetailPage);
