/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TWorkItemProperty,
  TWorkItemPropertyOption,
  TWorkItemPropertyOptionPayload,
  TWorkItemPropertyPayload,
  TWorkItemType,
} from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export class WorkItemTypeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getWorkItemTypes(workspaceSlug: string, projectId: string): Promise<TWorkItemType[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createWorkItemType(
    workspaceSlug: string,
    projectId: string,
    data: Partial<TWorkItemType>
  ): Promise<TWorkItemType> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorkItemType(
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    data: Partial<TWorkItemType>
  ): Promise<TWorkItemType> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${typeId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkItemType(workspaceSlug: string, projectId: string, typeId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${typeId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getWorkItemProperties(workspaceSlug: string, projectId: string): Promise<TWorkItemProperty[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createWorkItemProperty(
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    data: TWorkItemPropertyPayload
  ): Promise<TWorkItemProperty> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${typeId}/work-item-properties/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorkItemProperty(
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: TWorkItemPropertyPayload
  ): Promise<TWorkItemProperty> {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/${propertyId}/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkItemProperty(workspaceSlug: string, projectId: string, propertyId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/${propertyId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getWorkItemPropertyOption(
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string
  ): Promise<TWorkItemPropertyOption> {
    return this.get(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/${propertyId}/options/${optionId}/`
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createWorkItemPropertyOption(
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: TWorkItemPropertyOptionPayload
  ): Promise<TWorkItemPropertyOption> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/${propertyId}/options/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorkItemPropertyOption(
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string,
    data: TWorkItemPropertyOptionPayload
  ): Promise<TWorkItemPropertyOption> {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/${propertyId}/options/${optionId}/`,
      data
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkItemPropertyOption(
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string
  ): Promise<void> {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/${propertyId}/options/${optionId}/`
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
