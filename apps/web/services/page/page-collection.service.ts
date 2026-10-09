/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TPageCollection } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export class PageCollectionService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetchAll(workspaceSlug: string): Promise<TPageCollection[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/collections/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, data: Partial<TPageCollection>): Promise<TPageCollection> {
    return this.post(`/api/workspaces/${workspaceSlug}/collections/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(workspaceSlug: string, collectionId: string, data: Partial<TPageCollection>): Promise<TPageCollection> {
    return this.patch(`/api/workspaces/${workspaceSlug}/collections/${collectionId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  // the pages of a public collection move to the default collection; the API archives the ones of a private collection
  async remove(workspaceSlug: string, collectionId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/collections/${collectionId}/`, undefined, {
      params: {
        archive_pages: false,
      },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
