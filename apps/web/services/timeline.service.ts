/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TTimelineChanges, TTimelineDependencies } from "@plane/types";
// services
import { APIService } from "@/services/api.service";
import { fetchAroundOwnWrites } from "@/services/own-writes";

export class TimelineService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  // An answer that crossed a save of the page would put back the dates and dependencies from before that save.
  async getDependencies(workspaceSlug: string, projectId: string): Promise<TTimelineDependencies> {
    const url = `/api/workspaces/${workspaceSlug}/projects/${projectId}/timeline-dependencies/`;
    return fetchAroundOwnWrites(() => this.get(url))
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** Saves one operation on the timeline in one request; the answer holds what it saved, as stored. */
  async saveChanges(
    workspaceSlug: string,
    projectId: string,
    changes: TTimelineChanges
  ): Promise<TTimelineDependencies> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/timeline-dependencies/`, changes)
      .then((response) => response?.data)
      .catch((error) => {
        // without an answer of the server the reason is the failure of the request itself
        throw error?.response?.data ?? { error: error?.message };
      });
  }
}
