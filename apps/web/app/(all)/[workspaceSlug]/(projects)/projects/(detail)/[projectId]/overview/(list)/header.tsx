/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { ExpandableSearch } from "@makeplane/propel/components/expandable-search";
import { MilestoneOutline } from "@makeplane/propel/icons";
import { Breadcrumbs } from "@plane/blocks/breadcrumb";
import { Header } from "@plane/blocks/layout";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// components
import { CommonProjectBreadcrumbs } from "@/components/breadcrumbs/common";
import { useProjectCrumbProps } from "@/components/breadcrumbs/use-project-crumb-props";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { MilestoneCreateUpdateModal } from "@/components/milestones/milestone-modal";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";

export const MilestonesListHeader = observer(function MilestonesListHeader() {
  // router
  const { workspaceSlug, projectId } = useParams();
  const projectCrumb = useProjectCrumbProps(workspaceSlug?.toString(), projectId?.toString());
  // states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  // store hooks
  const { searchQuery, updateSearchQuery } = useMilestone();
  const { currentProjectDetails, loader } = useProject();
  const { allowPermissions } = useUserPermissions();
  // translation
  const { t } = useTranslation();
  // derived values
  const canUserCreateMilestone = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT
  );

  // the search text belongs to the list of one project
  useEffect(() => () => updateSearchQuery(""), [projectId, updateSearchQuery]);

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs isLoading={loader === "init-loader"}>
          <CommonProjectBreadcrumbs
            workspaceSlug={workspaceSlug?.toString()}
            projectId={projectId?.toString()}
            {...projectCrumb}
          />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("common.milestones")}
                href={`/${workspaceSlug}/projects/${projectId}/overview/`}
                icon={<MilestoneOutline className="h-4 w-4 text-tertiary" />}
                isLast
              />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
      {currentProjectDetails?.milestone_view && (
        <Header.RightItem>
          <ExpandableSearch
            size="lg"
            aria-label={t("common.search.label")}
            clearLabel={t("common.clear")}
            placeholder={t("common.search.label")}
            value={searchQuery}
            onValueChange={(value) => updateSearchQuery(value)}
          />
          {canUserCreateMilestone && (
            <>
              <MilestoneCreateUpdateModal
                workspaceSlug={workspaceSlug.toString()}
                projectId={currentProjectDetails.id}
                isOpen={isCreateModalOpen}
                handleClose={() => setIsCreateModalOpen(false)}
              />
              <Button
                variant="primary"
                size="md"
                stretch="auto"
                label={t("project_milestones.add_milestone")}
                onClick={() => setIsCreateModalOpen(true)}
              />
            </>
          )}
        </Header.RightItem>
      )}
    </Header>
  );
});
