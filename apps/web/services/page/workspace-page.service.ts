/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TDocumentPayload, TPage, TPageVersion, TWorkspacePagesResponse } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export class WorkspacePageService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetchAll(workspaceSlug: string, cursor?: string): Promise<TWorkspacePagesResponse> {
    return this.get(`/api/workspaces/${workspaceSlug}/pages/`, {
      params: {
        cursor,
      },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchById(workspaceSlug: string, pageId: string): Promise<TPage> {
    return this.get(`/api/workspaces/${workspaceSlug}/pages/${pageId}/`, {
      params: {
        track_visit: true,
      },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, data: Partial<TPage>): Promise<TPage> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(workspaceSlug: string, pageId: string, data: Partial<TPage>): Promise<TPage> {
    return this.patch(`/api/workspaces/${workspaceSlug}/pages/${pageId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async remove(workspaceSlug: string, pageId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/pages/${pageId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async archive(
    workspaceSlug: string,
    pageId: string
  ): Promise<{
    archived_at: string;
  }> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/${pageId}/archive/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async restore(workspaceSlug: string, pageId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/pages/${pageId}/archive/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async lock(workspaceSlug: string, pageId: string, recursive = false): Promise<void> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/${pageId}/lock/`, { recursive })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async unlock(workspaceSlug: string, pageId: string, recursive = false): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/pages/${pageId}/lock/`, { recursive })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchDescriptionBinary(workspaceSlug: string, pageId: string): Promise<ArrayBuffer> {
    return this.get(`/api/workspaces/${workspaceSlug}/pages/${pageId}/description/`, {
      headers: {
        "Content-Type": "application/octet-stream",
      },
      responseType: "arraybuffer",
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateDescription(workspaceSlug: string, pageId: string, data: TDocumentPayload): Promise<void> {
    return this.patch(`/api/workspaces/${workspaceSlug}/pages/${pageId}/description/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error;
      });
  }

  async duplicate(workspaceSlug: string, pageId: string): Promise<TPage> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/${pageId}/duplicate/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchAllVersions(workspaceSlug: string, pageId: string): Promise<TPageVersion[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/pages/${pageId}/versions/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchVersionById(workspaceSlug: string, pageId: string, versionId: string): Promise<TPageVersion> {
    return this.get(`/api/workspaces/${workspaceSlug}/pages/${pageId}/versions/${versionId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
