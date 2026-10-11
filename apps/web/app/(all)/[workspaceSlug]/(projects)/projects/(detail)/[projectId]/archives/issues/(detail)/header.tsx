/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// ui
import { ArchiveOutline, WorkItemsOutline } from "@makeplane/propel/icons";
import { Breadcrumbs } from "@plane/blocks/breadcrumb";
import { Header } from "@plane/blocks/layout";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { IssueDetailQuickActions } from "@/components/issues/issue-detail/issue-detail-quick-actions";
import { IssueTypeSwitcher } from "@/components/issues/issue-type-switcher";
// hooks
import { useProject } from "@/hooks/store/use-project";
// plane web
import { ProjectBreadcrumb } from "@/components/breadcrumbs/project";
import { useProjectCrumbProps } from "@/components/breadcrumbs/use-project-crumb-props";

export const ProjectArchivedIssueDetailsHeader = observer(function ProjectArchivedIssueDetailsHeader() {
  // router
  const { workspaceSlug, projectId, archivedIssueId } = useParams();
  const projectCrumb = useProjectCrumbProps(workspaceSlug?.toString(), projectId?.toString());
  // store hooks
  const { loader } = useProject();

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs isLoading={loader === "init-loader"}>
          <ProjectBreadcrumb
            workspaceSlug={workspaceSlug?.toString()}
            projectId={projectId?.toString()}
            {...projectCrumb}
          />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                href={`/${workspaceSlug}/projects/${projectId}/archives/issues`}
                label="Archives"
                icon={<ArchiveOutline className="h-4 w-4 text-tertiary" />}
              />
            }
          />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                href={`/${workspaceSlug}/projects/${projectId}/archives/issues`}
                label="Work items"
                icon={<WorkItemsOutline className="h-4 w-4 text-tertiary" />}
              />
            }
          />
          <Breadcrumbs.Item component={<IssueTypeSwitcher issueId={archivedIssueId.toString()} disabled />} />
        </Breadcrumbs>
      </Header.LeftItem>
      <Header.RightItem>
        <IssueDetailQuickActions
          workspaceSlug={workspaceSlug.toString()}
          projectId={projectId.toString()}
          issueId={archivedIssueId.toString()}
        />
      </Header.RightItem>
    </Header>
  );
});
