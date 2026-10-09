/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
// plane imports
import { WORK_ITEM_TYPES_PROPERTIES_AND_OPTIONS } from "@plane/constants";
import type { TIssueServiceType } from "@plane/types";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
import { useUserPermissions } from "@/hooks/store/user";

/**
 * A work item opens outside its project as well: from a workspace view, a profile, the home page. Those
 * routes have not fetched the types of its project, which define the properties it shows.
 */
export const useWorkItemProperties = (
  projectId: string | null | undefined,
  workspaceSlug: string | null | undefined,
  workItemId: string | null | undefined,
  _issueServiceType: TIssueServiceType
) => {
  const { fetchWorkItemTypes } = useWorkItemTypes();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();

  useSWR(
    projectId && workspaceSlug && workItemId
      ? WORK_ITEM_TYPES_PROPERTIES_AND_OPTIONS(
          projectId,
          getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId)
        )
      : null,
    projectId && workspaceSlug ? () => fetchWorkItemTypes(workspaceSlug, projectId) : null,
    { revalidateIfStale: false, revalidateOnFocus: false }
  );
};
