/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TIssue } from "./issue";

export type TIssueRelation = Record<TIssueRelationTypes, TIssue[]>;

export type TIssueRelationMap = {
  [issue_id: string]: Record<TIssueRelationTypes, string[]>;
};

export type TIssueRelationIdMap = Record<TIssueRelationTypes, string[]>;

export type TIssueRelationTypes =
  | "blocking"
  | "blocked_by"
  | "duplicate"
  | "relates_to"
  | "start_before"
  | "start_after"
  | "finish_before"
  | "finish_after";

export type TTimelineDependencyTypes = Extract<TIssueRelationTypes, "blocking" | "start_before" | "finish_before">;

export type TTimelineDependency = {
  id: string;
  predecessor_id: string;
  dependent_id: string;
  relation_type: TTimelineDependencyTypes;
  // days the dependency keeps between its work items on the timeline, 0 for none
  delay: number;
};

/** A work item at an end of a dependency, as `timeline-dependencies/` lists it. */
export type TTimelineIssue = {
  id: string;
  name: string;
  sequence_id: number;
  project_id: string;
  project__identifier: string;
  start_date: string | null;
  target_date: string | null;
  // false when the timeline computes the start from the dependencies that lead to the work item
  is_start_fixed: boolean;
};

export type TTimelineDependencies = { dependencies: TTimelineDependency[]; issues: TTimelineIssue[] };

/** What one operation on the timeline changed, as `timeline-dependencies/` saves it in one request. */
export type TTimelineChanges = {
  // created, or given this delay when the two work items have a dependency of this type
  dependencies: Omit<TTimelineDependency, "id">[];
  removed_dependencies: string[];
  // without dates when the work item was taken off the timeline
  issues: { id: string; start_date: string | null; target_date: string | null; is_start_fixed: boolean }[];
};
