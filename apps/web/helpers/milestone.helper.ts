/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { TMilestone } from "@plane/types";

export type TMilestoneState = "not_started" | "in_progress" | "done";

/** Share of the linked work items that are in a completed or cancelled state, in percent. */
export const getMilestoneProgress = (milestone: TMilestone): number =>
  milestone.total_issues > 0
    ? Math.round(((milestone.completed_issues + milestone.cancelled_issues) / milestone.total_issues) * 100)
    : 0;

export const getMilestoneState = (milestone: TMilestone): TMilestoneState => {
  const doneIssues = milestone.completed_issues + milestone.cancelled_issues;
  if (doneIssues === 0) return "not_started";
  return doneIssues === milestone.total_issues ? "done" : "in_progress";
};
