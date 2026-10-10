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
import type { ITimelineScheduleStore } from "@/store/timeline/schedule.store";
import { TimelineScheduleStore } from "@/store/timeline/schedule.store";

export interface IIssuesTimeLineStore extends IBaseTimelineStore {
  isDependencyEnabled: boolean;
  // observables
  dependencyMap: Record<string, TTimelineDependency[]>;
  // the computed plan of a project's timeline and the operations on it
  schedule: ITimelineScheduleStore;
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
  schedule: ITimelineScheduleStore;
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
    this.schedule = new TimelineScheduleStore(_rootStore, this);

    autorun(() => {
      const getIssueById = this.rootStore.issue.issues.getIssueById;
      this.updateBlocks(getIssueById);
    });
  }

  getProjectDependencies = computedFn(
    (projectId: string): TTimelineDependency[] => this.dependencyMap[projectId] ?? []
  );

  // the scheduling engine finds the conflicts of the timeline that is on the page
  getIsDependencyViolated = computedFn((dependency: TTimelineDependency): boolean => {
    const { projectId } = this.rootStore.router;
    return (
      !!projectId && this.schedule.getSchedule(projectId).conflicts.some(({ arrowId }) => arrowId === dependency.id)
    );
  });

  fetchDependencies = async (workspaceSlug: string, projectId: string) =>
    await this.timelineService.getDependencies(workspaceSlug, projectId).then((response) => {
      runInAction(() => {
        set(this.dependencyMap, [projectId], response.dependencies);
        this.schedule.setFetchedIssues(workspaceSlug, projectId, response.issues);
      });
      return response.dependencies;
    });
}
