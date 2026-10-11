/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { useTheme } from "next-themes";
import { useLocation, useNavigate } from "react-router";
import useSWR from "swr";
// plane imports
import { EIssueFilterType } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { EIssueLayoutTypes } from "@plane/types";
import { EIssuesStoreType } from "@plane/types";
// assets
import emptyIssueDark from "@/app/assets/empty-state/search/issues-dark.webp?url";
import emptyIssueLight from "@/app/assets/empty-state/search/issues-light.webp?url";
import PageNotFound from "@/app/not-found";
// components
import { ProjectAccessRestriction } from "@/components/auth-screens/project/project-access-restriction";
import { EmptyState } from "@/components/common/empty-state";
// helpers
import { getWorkItemsRoute, isSameProjectIdentifier, parseWorkItemsAddress } from "@/helpers/work-items-address.helper";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssues } from "@/hooks/store/use-issues";
import { useProject } from "@/hooks/store/use-project";
import { useAppRouter } from "@/hooks/use-app-router";
// services
import { ProjectService } from "@/services/project/project.service";
// local imports
import type { Route } from "./+types/page";

const projectService = new ProjectService();

/**
 * Where a short address of a project's work items arrives when the browser asks for it afresh: typed, followed
 * from outside, or reloaded. It finds the project that the address names and hands over to the page of that
 * project's work items, which the router knows by the project's id, keeping the short address in the browser.
 * See helpers/work-items-address.helper.ts.
 */
function WorkItemsAddressPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  // router
  const location = useLocation();
  const navigate = useNavigate();
  const router = useAppRouter();
  // hooks
  const { resolvedTheme } = useTheme();
  const { t } = useTranslation();
  // store hooks
  const { getProjectById, workspaceProjectIds, archivedProjectIds, loader } = useProject();
  const { issuesFilter } = useIssues(EIssuesStoreType.PROJECT);
  const { fetchIssueWithIdentifier } = useIssueDetail();
  // derived values
  const address = parseWorkItemsAddress(location.pathname);
  const areProjectsLoaded = loader !== "init-loader";
  const listedProject = [...(workspaceProjectIds ?? []), ...(archivedProjectIds ?? [])]
    .map((id) => getProjectById(id))
    .find((project) => project && address && isSameProjectIdentifier(project.identifier, address.projectIdentifier));
  const projectIdentifier = listedProject?.identifier ?? address?.projectIdentifier.toUpperCase();

  const findProjectId = async () => {
    if (!address || !projectIdentifier) return undefined;
    // a number that names no work item ends here, as it does on the page of one work item
    if (address.sequenceId)
      return (await fetchIssueWithIdentifier(workspaceSlug, projectIdentifier, address.sequenceId)).project_id;
    if (listedProject) return listedProject.id;
    // A project that the user is not shown in the list of projects may still exist. Its own page tells the user
    // what he may do about it, so the address leads there too.
    const { identifiers } = await projectService
      .checkProjectIdentifierAvailability(workspaceSlug, projectIdentifier)
      .catch(() => ({ identifiers: [] }));
    return identifiers[0]?.project as string | undefined;
  };

  // The layout that the address names is the project's layout before its page opens: the page would draw the
  // layout the user had last first, and drop what it had begun to load for it.
  const showLayout = async (projectId: string, layout: EIssueLayoutTypes) => {
    await issuesFilter.fetchFilters(workspaceSlug, projectId);
    if (issuesFilter.getIssueFilters(projectId)?.displayFilters?.layout !== layout)
      await issuesFilter.updateFilters(workspaceSlug, projectId, EIssueFilterType.DISPLAY_FILTERS, { layout });
  };

  const {
    data: projectId,
    error,
    isLoading,
  } = useSWR(
    // asked anew at every arrival: what a project's layout is must not come from an earlier one
    address && projectIdentifier && areProjectsLoaded ? `WORK_ITEMS_ADDRESS_${location.key}` : null,
    async () => {
      const foundProjectId = await findProjectId();
      // a project that the user may not open keeps its layout, and its own page says so
      if (foundProjectId && address?.layout) await showLayout(foundProjectId, address.layout).catch(() => {});
      return foundProjectId;
    },
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );

  useEffect(() => {
    if (!projectId) return;
    const { pathname, search, hash, state } = location;
    void navigate(
      { pathname: getWorkItemsRoute(workspaceSlug, projectId), search, hash },
      // the state of the entry goes along: after a reload it still holds the layout the entry had
      { replace: true, mask: { pathname, search, hash }, state }
    );
  }, [workspaceSlug, projectId, location, navigate]);

  if (!address) return <PageNotFound />;

  if (address.sequenceId && error)
    return (
      <EmptyState
        image={resolvedTheme === "dark" ? emptyIssueDark : emptyIssueLight}
        title={t("issue.empty_state.issue_detail.title")}
        description={t("issue.empty_state.issue_detail.description")}
        primaryButton={{
          text: t("issue.empty_state.issue_detail.primary_button.text"),
          onClick: () => router.push(`/${workspaceSlug}/workspace-views/all-issues/`),
        }}
      />
    );

  if (areProjectsLoaded && !isLoading && !projectId)
    return (
      <ProjectAccessRestriction
        errorStatusCode={404}
        isWorkspaceAdmin={false}
        handleJoinProject={() => {}}
        isJoinButtonDisabled
      />
    );

  return null;
}

export default observer(WorkItemsAddressPage);
