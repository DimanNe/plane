/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { IWorkspaceMember, TProjectMembership } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

/** A service user as a member: what the lists of the workspace's and of the project's members give of one. */
export type TServiceUserMember = {
  workspace_member: Required<Pick<IWorkspaceMember, "id" | "member" | "role" | "is_active" | "created_at">>;
  project_member: TProjectMembership;
};

export class ServiceUserService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  /** Makes the service user that the workspace has by this name a member of the project; without one, a new one. */
  async addToProject(workspaceSlug: string, projectId: string, name: string): Promise<TServiceUserMember> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/service-users/`, { name })
      .then((response) => response?.data)
      .catch((error) => {
        // without an answer of the server the reason is the failure of the request itself
        throw error?.response?.data ?? { error: error?.message };
      });
  }
}
