/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { MilestoneOutline } from "@makeplane/propel/icons";
import { Breadcrumbs } from "@plane/blocks/breadcrumb";
import { Header } from "@plane/blocks/layout";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// components
import { CommonProjectBreadcrumbs } from "@/components/breadcrumbs/common";
import { useProjectCrumbProps } from "@/components/breadcrumbs/use-project-crumb-props";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { MilestoneLinkWorkItems } from "@/components/milestones/detail/link-work-items";
import { MilestoneSelect } from "@/components/milestones/select";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";

export const MilestoneDetailHeader = observer(function MilestoneDetailHeader() {
  // router
  const router = useAppRouter();
  const { workspaceSlug, projectId, milestoneId } = useParams();
  const projectCrumb = useProjectCrumbProps(workspaceSlug?.toString(), projectId?.toString());
  // store hooks
  const { getMilestoneById } = useMilestone();
  const { loader } = useProject();
  const { allowPermissions } = useUserPermissions();
  // translation
  const { t } = useTranslation();
  // derived values
  const milestone = milestoneId ? getMilestoneById(milestoneId.toString()) : null;
  const canUserLinkWorkItems = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT
  );

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
              />
            }
          />
          <Breadcrumbs.Item
            component={
              <MilestoneSelect
                projectId={projectId?.toString()}
                value={milestoneId?.toString()}
                onChange={(id) => {
                  if (id) router.push(`/${workspaceSlug}/projects/${projectId}/overview/milestones/${id}`);
                }}
                variant="breadcrumb"
                placeholder={milestone?.title}
                clearable={false}
              />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
      {milestone && canUserLinkWorkItems && (
        <Header.RightItem>
          <MilestoneLinkWorkItems
            workspaceSlug={workspaceSlug.toString()}
            projectId={milestone.project}
            milestoneId={milestone.id}
          />
        </Header.RightItem>
      )}
    </Header>
  );
});
