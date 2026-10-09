/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { EmptyStateDetailed } from "@plane/blocks/empty-state";
import { EUserPermissionsLevel, PROJECT_MILESTONES } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EUserProjectRoles } from "@plane/types";
// components
import { PageHead } from "@/components/core/page-title";
import { MilestonesList } from "@/components/milestones/list";
import { MilestoneCreateUpdateModal } from "@/components/milestones/milestone-modal";
import { CycleModuleListLayoutLoader } from "@/components/ui/loader/cycle-module-list-loader";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
import type { Route } from "./+types/page";

function ProjectMilestonesPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  // states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  // router
  const router = useAppRouter();
  // store hooks
  const { getProjectMilestones, fetchMilestones } = useMilestone();
  const { getProjectById } = useProject();
  const { allowPermissions, getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  // translation
  const { t } = useTranslation();
  // derived values
  const project = getProjectById(projectId);
  const milestones = getProjectMilestones(projectId);
  const currentProjectRole = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId);
  const pageTitle = project?.name ? `${project.name} - ${t("common.milestones")}` : undefined;

  // the project fetches its milestones once; opening the list refreshes their progress
  useSWR(PROJECT_MILESTONES(projectId, currentProjectRole), () => fetchMilestones(workspaceSlug, projectId), {
    revalidateIfStale: false,
    revalidateOnFocus: false,
  });

  if (project?.milestone_view === false)
    return (
      <div className="h-full place-items-center">
        <EmptyStateDetailed
          assetKey="milestone"
          title={t("project_milestones.disabled.title")}
          description={t("project_milestones.disabled.description")}
          actions={[
            {
              label: t("project_settings.features.milestones.toggle_title"),
              onClick: () => router.push(`/${workspaceSlug}/settings/projects/${projectId}/features/milestones`),
              variant: "primary",
              disabled: !allowPermissions([EUserProjectRoles.ADMIN], EUserPermissionsLevel.PROJECT),
            },
          ]}
        />
      </div>
    );

  if (!milestones) return <CycleModuleListLayoutLoader />;

  return (
    <>
      <PageHead title={pageTitle} />
      <div className="h-full w-full">
        <MilestoneCreateUpdateModal
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          isOpen={isCreateModalOpen}
          handleClose={() => setIsCreateModalOpen(false)}
        />
        {milestones.length === 0 ? (
          <div className="h-full place-items-center">
            <EmptyStateDetailed
              assetKey="milestone"
              title={t("project_milestones.empty_state.title")}
              description={t("project_milestones.empty_state.description")}
              actions={[
                {
                  label: t("project_milestones.add_milestone"),
                  onClick: () => setIsCreateModalOpen(true),
                  variant: "primary",
                  disabled: !allowPermissions(
                    [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
                    EUserPermissionsLevel.PROJECT
                  ),
                },
              ]}
            />
          </div>
        ) : (
          <MilestonesList workspaceSlug={workspaceSlug} projectId={projectId} />
        )}
      </div>
    </>
  );
}

export default observer(ProjectMilestonesPage);
