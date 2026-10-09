/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TMilestone, TPaginatedResponse } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export class MilestoneService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getMilestones(workspaceSlug: string, projectId: string): Promise<TPaginatedResponse<TMilestone[]>> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createMilestone(workspaceSlug: string, projectId: string, data: Partial<TMilestone>): Promise<TMilestone> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async patchMilestone(
    workspaceSlug: string,
    projectId: string,
    milestoneId: string,
    data: Partial<TMilestone>
  ): Promise<TMilestone> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/${milestoneId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteMilestone(workspaceSlug: string, projectId: string, milestoneId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/${milestoneId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async addWorkItemsToMilestone(
    workspaceSlug: string,
    projectId: string,
    milestoneId: string,
    data: { issues: string[] }
  ): Promise<void> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/${milestoneId}/work-items/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
