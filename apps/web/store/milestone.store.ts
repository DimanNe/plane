/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { orderBy, set, sortBy } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// types
import type { TIssue, TMilestone } from "@plane/types";
// services
import { IssueService } from "@/services/issue";
import { MilestoneService } from "@/services/milestone.service";
// store
import type { CoreRootStore } from "./root.store";

export interface IMilestoneStore {
  // observables
  fetchedMap: Record<string, boolean>;
  milestoneMap: Record<string, TMilestone>;
  searchQuery: string;
  // computed actions
  getMilestoneById: (milestoneId: string) => TMilestone | null;
  getProjectMilestones: (projectId: string) => TMilestone[] | null;
  getFilteredMilestoneIds: (projectId: string) => string[] | null;
  getMilestoneWorkItemIds: (milestoneId: string) => string[];
  // actions
  updateSearchQuery: (query: string) => void;
  // fetch
  fetchMilestones: (workspaceSlug: string, projectId: string) => Promise<TMilestone[]>;
  fetchMilestoneWorkItems: (workspaceSlug: string, projectId: string, milestoneId: string) => Promise<TIssue[]>;
  // crud
  createMilestone: (workspaceSlug: string, projectId: string, data: Partial<TMilestone>) => Promise<TMilestone>;
  updateMilestone: (
    workspaceSlug: string,
    projectId: string,
    milestoneId: string,
    data: Partial<TMilestone>
  ) => Promise<TMilestone>;
  deleteMilestone: (workspaceSlug: string, projectId: string, milestoneId: string) => Promise<void>;
  // work items
  addWorkItemsToMilestone: (
    workspaceSlug: string,
    projectId: string,
    milestoneId: string,
    issueIds: string[]
  ) => Promise<void>;
}

export class MilestoneStore implements IMilestoneStore {
  // observables
  fetchedMap: Record<string, boolean> = {};
  milestoneMap: Record<string, TMilestone> = {};
  searchQuery: string = "";
  // root store
  rootStore;
  // services
  milestoneService;
  issueService;

  constructor(_rootStore: CoreRootStore) {
    makeObservable(this, {
      // observables
      fetchedMap: observable,
      milestoneMap: observable,
      searchQuery: observable.ref,
      // actions
      updateSearchQuery: action,
      fetchMilestones: action,
      fetchMilestoneWorkItems: action,
      createMilestone: action,
      updateMilestone: action,
      deleteMilestone: action,
      addWorkItemsToMilestone: action,
    });

    this.rootStore = _rootStore;

    // services
    this.milestoneService = new MilestoneService();
    this.issueService = new IssueService();
  }

  getMilestoneById = computedFn((milestoneId: string): TMilestone | null => this.milestoneMap[milestoneId] ?? null);

  // by target date, earliest first and undated last
  getProjectMilestones = computedFn((projectId: string): TMilestone[] | null => {
    if (!this.fetchedMap[projectId]) return null;
    const milestones = Object.values(this.milestoneMap).filter((m) => m.project === projectId);
    return orderBy(milestones, [(m) => !m.target_date, "target_date", "created_at"], ["asc", "asc", "desc"]);
  });

  getFilteredMilestoneIds = computedFn((projectId: string): string[] | null => {
    const milestones = this.getProjectMilestones(projectId);
    if (!milestones) return null;
    return milestones.filter((m) => m.title.toLowerCase().includes(this.searchQuery.toLowerCase())).map((m) => m.id);
  });

  // derived from the work item store, so a work item that changes its milestone anywhere moves here too
  getMilestoneWorkItemIds = computedFn((milestoneId: string): string[] => {
    const workItems = Object.values(this.rootStore.issue.issues.issuesMap).filter(
      (issue) => issue.milestone_id === milestoneId && !issue.archived_at
    );
    return sortBy(workItems, [(issue) => issue.sort_order]).map((issue) => issue.id);
  });

  updateSearchQuery = (query: string) => {
    this.searchQuery = query;
  };

  fetchMilestones = async (workspaceSlug: string, projectId: string) =>
    await this.milestoneService.getMilestones(workspaceSlug, projectId).then((response) => {
      runInAction(() => {
        Object.values(this.milestoneMap).forEach((milestone) => {
          if (milestone.project === projectId) delete this.milestoneMap[milestone.id];
        });
        response.results.forEach((milestone) => {
          set(this.milestoneMap, [milestone.id], milestone);
        });
        set(this.fetchedMap, projectId, true);
      });
      return response.results;
    });

  fetchMilestoneWorkItems = async (workspaceSlug: string, projectId: string, milestoneId: string) =>
    await this.issueService
      .getIssues(workspaceSlug, projectId, { filters: JSON.stringify({ milestone_id: milestoneId }) })
      .then((response) => {
        const workItems = response.results as TIssue[];
        this.rootStore.issue.issues.addIssue(workItems);
        return workItems;
      });

  createMilestone = async (workspaceSlug: string, projectId: string, data: Partial<TMilestone>) =>
    await this.milestoneService.createMilestone(workspaceSlug, projectId, data).then((response) => {
      runInAction(() => {
        set(this.milestoneMap, [response.id], response);
      });
      return response;
    });

  updateMilestone = async (workspaceSlug: string, projectId: string, milestoneId: string, data: Partial<TMilestone>) =>
    await this.milestoneService.patchMilestone(workspaceSlug, projectId, milestoneId, data).then((response) => {
      runInAction(() => {
        set(this.milestoneMap, [milestoneId], response);
      });
      return response;
    });

  deleteMilestone = async (workspaceSlug: string, projectId: string, milestoneId: string) => {
    await this.milestoneService.deleteMilestone(workspaceSlug, projectId, milestoneId);
    runInAction(() => {
      delete this.milestoneMap[milestoneId];
      this.getMilestoneWorkItemIds(milestoneId).forEach((issueId) => {
        this.rootStore.issue.issues.updateIssue(issueId, { milestone_id: null });
      });
    });
  };

  addWorkItemsToMilestone = async (
    workspaceSlug: string,
    projectId: string,
    milestoneId: string,
    issueIds: string[]
  ) => {
    await this.milestoneService.addWorkItemsToMilestone(workspaceSlug, projectId, milestoneId, { issues: issueIds });
    // the linked work items may not be loaded yet, and a moved one changes the counts of two milestones
    await Promise.all([
      this.fetchMilestoneWorkItems(workspaceSlug, projectId, milestoneId),
      this.fetchMilestones(workspaceSlug, projectId),
    ]);
  };
}
