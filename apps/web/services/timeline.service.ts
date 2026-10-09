/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TTimelineDependency } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export class TimelineService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getDependencies(workspaceSlug: string, projectId: string): Promise<{ dependencies: TTimelineDependency[] }> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/timeline-dependencies/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
