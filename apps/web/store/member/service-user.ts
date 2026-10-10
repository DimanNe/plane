/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set, uniq, update } from "lodash-es";
import { runInAction } from "mobx";
// services
import { ServiceUserService } from "@/services/service-user.service";
// stores
import type { IMemberRootStore } from "@/store/member";
import type { IProjectStore } from "@/store/project/project.store";

const serviceUserService = new ServiceUserService();

/**
 * A service user stands for an agent: work items are assigned to it, and nobody signs in as it.
 *
 * Makes the service user with this name a member of the project and returns its id. The answer holds what the
 * lists of members would give of it, so it is among the members of the page at once, without asking for the lists.
 */
export const addServiceUserToProject = async (
  memberRoot: IMemberRootStore,
  projectStore: IProjectStore,
  workspaceSlug: string,
  projectId: string,
  name: string
): Promise<string> => {
  const { workspace_member, project_member } = await serviceUserService.addToProject(workspaceSlug, projectId, name);
  const user = workspace_member.member;
  runInAction(() => {
    set(memberRoot.memberMap, user.id, { ...user, joining_date: workspace_member.created_at });
    set(memberRoot.workspace.workspaceMemberMap, [workspaceSlug, user.id], {
      id: workspace_member.id,
      member: user.id,
      role: workspace_member.role,
      is_active: workspace_member.is_active,
    });
    set(memberRoot.project.projectMemberMap, [projectId, user.id], project_member);
    if (!projectStore.projectMap[projectId]) return;
    update(projectStore.projectMap, [projectId, "members"], (memberIds: string[] = []) =>
      uniq([...memberIds, user.id])
    );
  });
  return user.id;
};
