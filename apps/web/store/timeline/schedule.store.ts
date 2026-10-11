/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, makeObservable, observable, runInAction, when } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import { computeSchedule, getChanges, getPlan } from "@plane/blocks/timeline-schedule";
import type { TPlan, TSchedule, TStoredTask } from "@plane/blocks/timeline-schedule";
import { setToast } from "@plane/blocks/toast";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import type { TTimelineDependencies, TTimelineDependency, TTimelineIssue } from "@plane/types";
// services
import { TimelineService } from "@/services/timeline.service";
// store
import type { RootStore } from "@/store/root.store";

/**
 * One operation on the timeline of a project: a copy of the plan that a gesture changes and the page previews.
 * `stored` is what the plan was made of; saving sends what the plan changed of it.
 */
export type TTimelineOperation = {
  workspaceSlug: string;
  projectId: string;
  stored: { tasks: TStoredTask[]; dependencies: TTimelineDependency[] };
  plan: TPlan;
  schedule: TSchedule;
  isSaving: boolean;
};

export interface ITimelineScheduleStore {
  // observables
  operation: TTimelineOperation | undefined;
  // computed functions
  getPlan: (projectId: string) => TPlan;
  getSchedule: (projectId: string) => TSchedule;
  getChangingArrowIds: (projectId: string) => string[];
  getHeldProjectIds: (workspaceSlug: string) => string[];
  isPlanComputedFrom: (projectId: string, table: string, id: string) => boolean;
  // actions
  fetchStored: (workspaceSlug: string, projectId: string) => Promise<TTimelineDependencies>;
  setFetchedIssues: (workspaceSlug: string, projectId: string, issues: TTimelineIssue[]) => void;
  beginOperation: (workspaceSlug: string, projectId: string) => TPlan | undefined;
  previewOperation: (plan: TPlan) => TSchedule;
  commitOperation: () => Promise<boolean>;
  abortOperation: () => void;
}

// one list for every time there is none, so that what reads it is not drawn again
const NO_ARROW_IDS: string[] = [];

const getReason = (error: unknown): string => {
  if (error instanceof Error) return error.message;
  const answer = error as { error?: string; message?: string; detail?: string } | undefined;
  return answer?.error ?? answer?.message ?? answer?.detail ?? JSON.stringify(error);
};

/**
 * The plan of a project's timeline and the operations on it. The scheduling engine computes; this store gives
 * it what the page holds, shows what it computed, and saves an operation in one request.
 */
export class TimelineScheduleStore implements ITimelineScheduleStore {
  // the work items at the ends of each project's dependencies, as the server listed them
  issueMap: Record<string, Record<string, TTimelineIssue>> = {};
  operation: TTimelineOperation | undefined = undefined;
  // the workspace of each project whose plan the page holds
  workspaceSlugs: Record<string, string> = {};
  // services
  timelineService = new TimelineService();

  constructor(
    private rootStore: RootStore,
    private timeline: { dependencyMap: Record<string, TTimelineDependency[]> }
  ) {
    makeObservable(this, {
      // observables
      issueMap: observable,
      operation: observable.ref,
      // actions
      setFetchedIssues: action,
      beginOperation: action,
      previewOperation: action,
      abortOperation: action,
    });
  }

  /**
   * The work items of the project that the page holds, and those at the other end of its dependencies. The dates
   * are the ones every other view shows; whether a start is fixed is known only for an end of a dependency, and
   * matters only there.
   *
   * A work item of another project is fixed here on its stored dates: the page does not hold the arrows that
   * lead to it inside its own project, so only a timeline of that project can compute it. Computed here from
   * some of its arrows, it would be saved with other dates than there, and two open pages would save it in turn
   * without end.
   */
  private getStoredTasks = (projectId: string): TStoredTask[] => {
    const issuesMap = this.rootStore.issue.issues.issuesMap;
    const fetched = this.issueMap[projectId] ?? {};
    const issueIds = Object.keys(issuesMap).filter((id) => !fetched[id] && issuesMap[id].project_id === projectId);
    return [...Object.keys(fetched), ...issueIds].map((id) => {
      const { start_date, target_date } = issuesMap[id] ?? fetched[id];
      const isFollowing = fetched[id]?.project_id === projectId && !fetched[id].is_start_fixed;
      return { id, start_date, target_date, is_start_fixed: !isFollowing };
    });
  };

  private getStored = (projectId: string) => ({
    tasks: this.getStoredTasks(projectId),
    dependencies: this.timeline.dependencyMap[projectId] ?? [],
  });

  private getStoredPlan = computedFn((projectId: string): TPlan => {
    const { tasks, dependencies } = this.getStored(projectId);
    return getPlan(tasks, dependencies);
  });

  /** The plan the timeline of the project shows: the operation's while one is going on, else the stored one. */
  getPlan = computedFn(
    (projectId: string): TPlan =>
      this.operation?.projectId === projectId ? this.operation.plan : this.getStoredPlan(projectId)
  );

  /**
   * The arrows whose days the operation that is going on has changed, and those it has added: what a move of a
   * task makes count. None without an operation, and none while it is being saved: the gesture is over then.
   */
  getChangingArrowIds = computedFn((projectId: string): string[] => {
    if (this.operation?.projectId !== projectId || this.operation.isSaving) return NO_ARROW_IDS;
    const storedDelays = new Map(this.getStoredPlan(projectId).arrows.map((arrow) => [arrow.id, arrow.delay]));
    return this.operation.plan.arrows.flatMap((arrow) =>
      storedDelays.get(arrow.id) === arrow.delay ? [] : [arrow.id]
    );
  });

  /**
   * The schedule of that plan: the preview of the operation while one is going on. Stored arrows that cannot be
   * computed leave every task on its stored dates; `beginOperation` tells why.
   */
  getSchedule = computedFn((projectId: string): TSchedule => {
    if (this.operation?.projectId === projectId) return this.operation.schedule;
    const plan = this.getStoredPlan(projectId);
    try {
      return computeSchedule(plan.tasks, plan.arrows);
    } catch {
      return computeSchedule(getPlan(this.getStoredTasks(projectId), []).tasks, []);
    }
  });

  /** The projects of the workspace whose timeline the page has loaded: it holds their plans from then on. */
  getHeldProjectIds = (workspaceSlug: string): string[] =>
    Object.keys(this.workspaceSlugs).filter((projectId) => this.workspaceSlugs[projectId] === workspaceSlug);

  /**
   * Whether a changed record is one that the plan of the project is computed from: a relation, wherever it was
   * made (a new one can lead to the project from another), and a work item at an end of the project's
   * dependencies. The dates of the project's other work items reach the plan with the list that shows them.
   */
  isPlanComputedFrom = (projectId: string, table: string, id: string): boolean =>
    table === "issue_relations" || (table === "issues" && !!this.issueMap[projectId]?.[id]);

  /**
   * Asks the server for what the plan of the project is computed from. An operation works on a copy of the plan,
   * so no answer is taken while one is going on. An answer that came during one is asked for again when it has
   * ended: the operation may have saved since.
   */
  fetchStored = async (workspaceSlug: string, projectId: string): Promise<TTimelineDependencies> => {
    await when(() => !this.operation);
    const fetched = await this.timelineService.getDependencies(workspaceSlug, projectId);
    return this.operation ? this.fetchStored(workspaceSlug, projectId) : fetched;
  };

  private mergeIssues = (projectId: string, issues: TTimelineIssue[]) => {
    const { getIssueById, updateIssue } = this.rootStore.issue.issues;
    for (const issue of issues) {
      set(this.issueMap, [projectId, issue.id], issue);
      const { start_date, target_date } = issue;
      const shown = getIssueById(issue.id);
      if (shown && (shown.start_date !== start_date || shown.target_date !== target_date))
        updateIssue(issue.id, { start_date, target_date });
    }
  };

  /**
   * Takes the work items the server listed with the project's dependencies; the timeline has loaded then. When
   * the stored dates differ from what the plan computes (somebody changed a date or a dependency elsewhere), the
   * computed dates are saved as an operation is.
   */
  setFetchedIssues = (workspaceSlug: string, projectId: string, issues: TTimelineIssue[]) => {
    this.workspaceSlugs[projectId] = workspaceSlug;
    set(this.issueMap, [projectId], {});
    this.mergeIssues(projectId, issues);
    const canEdit = this.rootStore.user.permission.allowPermissions(
      [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
      EUserPermissionsLevel.PROJECT,
      workspaceSlug,
      projectId
    );
    if (canEdit && !this.operation && this.beginOperation(workspaceSlug, projectId)) void this.commitOperation();
  };

  /**
   * Starts an operation on the tasks and arrows the page holds, and returns the plan for the gesture functions
   * to change. Returns nothing while the previous operation is being saved, and when the stored arrows cannot be
   * computed (a toast tells why).
   */
  beginOperation = (workspaceSlug: string, projectId: string): TPlan | undefined => {
    if (this.operation?.isSaving) return undefined;
    const stored = this.getStored(projectId);
    const plan = getPlan(stored.tasks, stored.dependencies);
    try {
      const schedule = computeSchedule(plan.tasks, plan.arrows);
      this.operation = { workspaceSlug, projectId, stored, plan, schedule, isSaving: false };
      return plan;
    } catch (error) {
      // the engine names tasks by id; a person knows them by key and name
      const reason = Object.values(this.issueMap[projectId] ?? {}).reduce(
        (text, issue) => text.replaceAll(issue.id, `${issue.project__identifier}-${issue.sequence_id} ${issue.name}`),
        getReason(error)
      );
      setToast({ type: "error", title: reason });
      return undefined;
    }
  };

  /** Shows a changed copy of the operation's plan and returns its schedule. Nothing is saved. */
  previewOperation = (plan: TPlan): TSchedule => {
    const schedule = computeSchedule(plan.tasks, plan.arrows);
    if (this.operation && !this.operation.isSaving) this.operation = { ...this.operation, plan, schedule };
    return schedule;
  };

  /**
   * Saves the plan last previewed in one request: the changed parameters and the dates of every task that moved.
   * The preview stays on the page until the server answered. Then the stores take what was saved, so every other
   * view shows it; when the request fails the preview is dropped, nothing has changed, and a toast gives the
   * reason of the server. Resolves to whether the operation was saved.
   */
  commitOperation = async (): Promise<boolean> => {
    const operation = this.operation;
    if (!operation || operation.isSaving) return false;
    const { workspaceSlug, projectId, stored, plan } = operation;
    const changes = getChanges(stored.tasks, stored.dependencies, plan);
    if (changes.dependencies.length + changes.removed_dependencies.length + changes.issues.length === 0) {
      this.abortOperation();
      return true;
    }
    runInAction(() => {
      this.operation = { ...operation, isSaving: true };
    });
    try {
      const saved = await this.timelineService.saveChanges(workspaceSlug, projectId, changes);
      runInAction(() => {
        const replacedIds = new Set([...changes.removed_dependencies, ...saved.dependencies.map(({ id }) => id)]);
        const kept = this.getStored(projectId).dependencies.filter(({ id }) => !replacedIds.has(id));
        set(this.timeline.dependencyMap, [projectId], [...kept, ...saved.dependencies]);
        this.mergeIssues(projectId, saved.issues);
        this.operation = undefined;
      });
      return true;
    } catch (error) {
      this.abortOperation();
      setToast({ type: "error", title: getReason(error) });
      return false;
    }
  };

  /** Drops the operation and its preview. Nothing else happens: the stored parameters are as they were. */
  abortOperation = () => {
    this.operation = undefined;
  };
}
