/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { omit, set, sortBy } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import { WORK_ITEM_PROPERTY_KEY_PREFIX } from "@plane/constants";
import type {
  TWorkItemProperty,
  TWorkItemPropertyOption,
  TWorkItemPropertyOptionPayload,
  TWorkItemPropertyPayload,
  TWorkItemType,
} from "@plane/types";
// services
import { WorkItemTypeService } from "@/services/work-item-type.service";
// store
import type { CoreRootStore } from "./root.store";

export interface IWorkItemTypeStore {
  // observables
  typesByProjectId: Record<string, TWorkItemType[]>;
  propertyMap: Record<string, TWorkItemProperty>;
  // computed actions
  getProjectWorkItemTypes: (projectId: string | null | undefined) => TWorkItemType[] | undefined;
  getWorkItemTypeById: (
    projectId: string | null | undefined,
    typeId: string | null | undefined
  ) => TWorkItemType | undefined;
  getWorkItemTypeProperties: (typeId: string | null | undefined) => TWorkItemProperty[];
  getProjectWorkItemProperties: (projectId: string | null | undefined) => TWorkItemProperty[];
  getWorkItemPropertyByKey: (propertyKey: string) => TWorkItemProperty | undefined;
  // fetch actions
  fetchWorkItemTypes: (workspaceSlug: string, projectId: string) => Promise<TWorkItemType[]>;
  fetchWorkItemPropertyOption: (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string
  ) => Promise<TWorkItemPropertyOption>;
  // crud actions
  enableWorkItemTypes: (workspaceSlug: string, projectId: string) => Promise<void>;
  createWorkItemType: (
    workspaceSlug: string,
    projectId: string,
    data: Partial<TWorkItemType>
  ) => Promise<TWorkItemType>;
  updateWorkItemType: (
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    data: Partial<TWorkItemType>
  ) => Promise<TWorkItemType>;
  deleteWorkItemType: (workspaceSlug: string, projectId: string, typeId: string) => Promise<void>;
  createWorkItemProperty: (
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    data: TWorkItemPropertyPayload
  ) => Promise<TWorkItemProperty>;
  updateWorkItemProperty: (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: TWorkItemPropertyPayload
  ) => Promise<TWorkItemProperty>;
  deleteWorkItemProperty: (workspaceSlug: string, projectId: string, propertyId: string) => Promise<void>;
  createWorkItemPropertyOption: (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: TWorkItemPropertyOptionPayload
  ) => Promise<TWorkItemPropertyOption>;
  updateWorkItemPropertyOption: (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string,
    data: TWorkItemPropertyOptionPayload
  ) => Promise<TWorkItemPropertyOption>;
  deleteWorkItemPropertyOption: (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string
  ) => Promise<void>;
}

export class WorkItemTypeStore implements IWorkItemTypeStore {
  // observables
  typesByProjectId: Record<string, TWorkItemType[]> = {};
  propertyMap: Record<string, TWorkItemProperty> = {};
  // root store
  rootStore;
  // services
  workItemTypeService;

  constructor(_rootStore: CoreRootStore) {
    makeObservable(this, {
      typesByProjectId: observable,
      propertyMap: observable,
      fetchWorkItemTypes: action,
      enableWorkItemTypes: action,
      createWorkItemType: action,
      updateWorkItemType: action,
      deleteWorkItemType: action,
      createWorkItemProperty: action,
      updateWorkItemProperty: action,
      deleteWorkItemProperty: action,
      createWorkItemPropertyOption: action,
      updateWorkItemPropertyOption: action,
      deleteWorkItemPropertyOption: action,
    });
    // root store
    this.rootStore = _rootStore;
    // services
    this.workItemTypeService = new WorkItemTypeService();
  }

  getProjectWorkItemTypes = computedFn((projectId: string | null | undefined) =>
    projectId ? this.typesByProjectId[projectId] : undefined
  );

  getWorkItemTypeById = computedFn((projectId: string | null | undefined, typeId: string | null | undefined) =>
    this.getProjectWorkItemTypes(projectId)?.find((type) => type.id === typeId)
  );

  /**
   * Returns the properties of a type in their order. A type deleted from its project keeps its properties,
   * as do the work items that still have the type.
   */
  getWorkItemTypeProperties = computedFn((typeId: string | null | undefined) =>
    sortBy(
      Object.values(this.propertyMap).filter((property) => property.issue_type === typeId),
      "sort_order"
    )
  );

  getProjectWorkItemProperties = computedFn((projectId: string | null | undefined) =>
    (this.getProjectWorkItemTypes(projectId) ?? []).flatMap((type) => this.getWorkItemTypeProperties(type.id))
  );

  /**
   * Returns the property a display property key stands for, if it stands for one
   */
  getWorkItemPropertyByKey = computedFn(
    (propertyKey: string): TWorkItemProperty | undefined =>
      this.propertyMap[propertyKey.replace(WORK_ITEM_PROPERTY_KEY_PREFIX, "")]
  );

  /**
   * Fetches the types of a project and the properties of all of them, options included
   * @param workspaceSlug
   * @param projectId
   */
  fetchWorkItemTypes = async (workspaceSlug: string, projectId: string) => {
    const [types, properties] = await Promise.all([
      this.workItemTypeService.getWorkItemTypes(workspaceSlug, projectId),
      this.workItemTypeService.getWorkItemProperties(workspaceSlug, projectId),
    ]);
    runInAction(() => {
      set(this.typesByProjectId, [projectId], types);
      for (const property of Object.values(this.propertyMap))
        if (property.project === projectId) delete this.propertyMap[property.id];
      for (const property of properties) set(this.propertyMap, [property.id], property);
    });
    return types;
  };

  /**
   * Returns one option with the number of work items that selected it
   */
  fetchWorkItemPropertyOption = async (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string
  ) => await this.workItemTypeService.getWorkItemPropertyOption(workspaceSlug, projectId, propertyId, optionId);

  /**
   * Enables types for a project, which creates its first types on the server. It cannot be undone.
   * @param workspaceSlug
   * @param projectId
   */
  enableWorkItemTypes = async (workspaceSlug: string, projectId: string) => {
    await this.rootStore.projectRoot.project.updateProject(workspaceSlug, projectId, { is_issue_type_enabled: true });
    const types = await this.fetchWorkItemTypes(workspaceSlug, projectId);
    // the server has given the default type to the work items of the project; so have the loaded ones
    const defaultTypeId = types.find((type) => type.is_default)?.id;
    const { issuesMap, updateIssue } = this.rootStore.issue.issues;
    for (const workItem of Object.values(issuesMap))
      if (defaultTypeId && workItem.project_id === projectId && !workItem.type_id)
        updateIssue(workItem.id, { type_id: defaultTypeId });
  };

  /**
   * Puts a created or updated item into its list. A project has one default type and a single-select
   * property one default option: the server takes the mark from the others when it gives it to an item,
   * and so does the store.
   */
  private upsertItem = <T extends { id: string; is_default: boolean }>(items: T[], item: T, hasOneDefault: boolean) => {
    const index = items.findIndex((other) => other.id === item.id);
    if (index === -1) items.push(item);
    else items[index] = item;
    if (item.is_default && hasOneDefault) for (const other of items) if (other.id !== item.id) other.is_default = false;
  };

  createWorkItemType = async (workspaceSlug: string, projectId: string, data: Partial<TWorkItemType>) => {
    const type = await this.workItemTypeService.createWorkItemType(workspaceSlug, projectId, data);
    runInAction(() => {
      this.upsertItem(this.typesByProjectId[projectId], type, true);
    });
    return type;
  };

  updateWorkItemType = async (
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    data: Partial<TWorkItemType>
  ) => {
    const type = await this.workItemTypeService.updateWorkItemType(workspaceSlug, projectId, typeId, data);
    runInAction(() => {
      this.upsertItem(this.typesByProjectId[projectId], type, true);
    });
    return type;
  };

  deleteWorkItemType = async (workspaceSlug: string, projectId: string, typeId: string) => {
    await this.workItemTypeService.deleteWorkItemType(workspaceSlug, projectId, typeId);
    runInAction(() => {
      set(
        this.typesByProjectId,
        [projectId],
        (this.typesByProjectId[projectId] ?? []).filter((type) => type.id !== typeId)
      );
    });
  };

  createWorkItemProperty = async (
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    data: TWorkItemPropertyPayload
  ) => {
    const property = await this.workItemTypeService.createWorkItemProperty(workspaceSlug, projectId, typeId, data);
    runInAction(() => {
      set(this.propertyMap, [property.id], property);
    });
    return property;
  };

  /**
   * Updates a property. The store has the change at once, which a moved property needs to stay where it
   * was dropped, and goes back to what it had when the server refuses.
   */
  updateWorkItemProperty = async (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: TWorkItemPropertyPayload
  ) => {
    const propertyBeforeUpdate = this.propertyMap[propertyId];
    try {
      runInAction(() => {
        set(this.propertyMap, [propertyId], { ...propertyBeforeUpdate, ...omit(data, "options") });
      });
      const property = await this.workItemTypeService.updateWorkItemProperty(
        workspaceSlug,
        projectId,
        propertyId,
        data
      );
      runInAction(() => {
        set(this.propertyMap, [propertyId], property);
      });
      // deleting a level of a cascading property deletes the options below the levels that are left
      const deletedOptionIds = propertyBeforeUpdate.options
        .filter((option) => !property.options.some((other) => other.id === option.id))
        .map((option) => option.id);
      if (deletedOptionIds.length) this.removeOptionsFromWorkItems(propertyId, deletedOptionIds);
      return property;
    } catch (error) {
      runInAction(() => {
        set(this.propertyMap, [propertyId], propertyBeforeUpdate);
      });
      throw error;
    }
  };

  deleteWorkItemProperty = async (workspaceSlug: string, projectId: string, propertyId: string) => {
    await this.workItemTypeService.deleteWorkItemProperty(workspaceSlug, projectId, propertyId);
    runInAction(() => {
      delete this.propertyMap[propertyId];
    });
  };

  createWorkItemPropertyOption = async (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: TWorkItemPropertyOptionPayload
  ) => {
    const option = await this.workItemTypeService.createWorkItemPropertyOption(
      workspaceSlug,
      projectId,
      propertyId,
      data
    );
    this.setPropertyOption(propertyId, option);
    return option;
  };

  updateWorkItemPropertyOption = async (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string,
    data: TWorkItemPropertyOptionPayload
  ) => {
    const option = await this.workItemTypeService.updateWorkItemPropertyOption(
      workspaceSlug,
      projectId,
      propertyId,
      optionId,
      data
    );
    this.setPropertyOption(propertyId, option);
    return option;
  };

  deleteWorkItemPropertyOption = async (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string
  ) => {
    await this.workItemTypeService.deleteWorkItemPropertyOption(workspaceSlug, projectId, propertyId, optionId);
    const options = this.propertyMap[propertyId]?.options ?? [];
    // an option of a cascading property is deleted with the options under it, which the loop goes on to
    const deletedOptionIds = [optionId];
    for (const deletedOptionId of deletedOptionIds)
      for (const option of options) if (option.parent === deletedOptionId) deletedOptionIds.push(option.id);
    runInAction(() => {
      if (this.propertyMap[propertyId])
        set(
          this.propertyMap,
          [propertyId, "options"],
          options.filter((option) => !deletedOptionIds.includes(option.id))
        );
    });
    this.removeOptionsFromWorkItems(propertyId, deletedOptionIds);
  };

  /**
   * The server takes deleted options out of the work items that had selected them; so does the store with
   * the loaded ones.
   */
  private removeOptionsFromWorkItems = (propertyId: string, optionIds: string[]) => {
    const { issuesMap, updateIssue } = this.rootStore.issue.issues;
    for (const workItem of Object.values(issuesMap)) {
      const value = workItem.custom_properties?.[propertyId];
      const selectedIds = Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
      const remainingIds = selectedIds.filter((id) => !optionIds.includes(id));
      if (remainingIds.length === selectedIds.length) continue;
      updateIssue(workItem.id, {
        custom_properties: { ...workItem.custom_properties, [propertyId]: remainingIds.length ? remainingIds : null },
      });
    }
  };

  private setPropertyOption = (propertyId: string, option: TWorkItemPropertyOption) => {
    runInAction(() => {
      const property = this.propertyMap[propertyId];
      if (property) this.upsertItem(property.options, option, !property.is_multi);
    });
  };
}
