/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, autorun, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import type { TTimelineDependency } from "@plane/types";
// services
import { TimelineService } from "@/services/timeline.service";
// store
import type { RootStore } from "@/store/root.store";
import type { IBaseTimelineStore } from "@/store/timeline/base-timeline.store";
import { BaseTimeLineStore } from "@/store/timeline/base-timeline.store";

export interface IIssuesTimeLineStore extends IBaseTimelineStore {
  isDependencyEnabled: boolean;
  // observables
  dependencyMap: Record<string, TTimelineDependency[]>;
  // computed functions
  getProjectDependencies: (projectId: string) => TTimelineDependency[];
  getIsDependencyViolated: (dependency: TTimelineDependency) => boolean;
  // actions
  fetchDependencies: (workspaceSlug: string, projectId: string) => Promise<TTimelineDependency[]>;
}

export class IssuesTimeLineStore extends BaseTimeLineStore implements IIssuesTimeLineStore {
  isDependencyEnabled = true;
  // observables
  dependencyMap: Record<string, TTimelineDependency[]> = {};
  // services
  timelineService;

  constructor(_rootStore: RootStore) {
    super(_rootStore);

    makeObservable(this, {
      // observables
      dependencyMap: observable,
      // actions
      fetchDependencies: action,
    });

    this.timelineService = new TimelineService();

    autorun(() => {
      const getIssueById = this.rootStore.issue.issues.getIssueById;
      this.updateBlocks(getIssueById);
    });
  }

  getProjectDependencies = computedFn(
    (projectId: string): TTimelineDependency[] => this.dependencyMap[projectId] ?? []
  );

  // the dependent work item starts or finishes before the date its predecessor allows;
  // a dependency constrains only work items that have both dates
  getIsDependencyViolated = computedFn((dependency: TTimelineDependency): boolean => {
    const predecessor = this.rootStore.issue.issues.getIssueById(dependency.predecessor_id);
    const dependent = this.rootStore.issue.issues.getIssueById(dependency.dependent_id);
    if (!predecessor?.start_date || !predecessor.target_date || !dependent?.start_date || !dependent.target_date)
      return false;
    const predecessorDate =
      dependency.relation_type === "start_before" ? predecessor.start_date : predecessor.target_date;
    const dependentDate = dependency.relation_type === "finish_before" ? dependent.target_date : dependent.start_date;
    return dependentDate < predecessorDate;
  });

  fetchDependencies = async (workspaceSlug: string, projectId: string) =>
    await this.timelineService.getDependencies(workspaceSlug, projectId).then((response) => {
      runInAction(() => {
        set(this.dependencyMap, [projectId], response.dependencies);
      });
      return response.dependencies;
    });
}
