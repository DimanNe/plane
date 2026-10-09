/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TIssueRelationTypes } from "@plane/types";

export const REVERSE_RELATIONS: { [key in TIssueRelationTypes]: TIssueRelationTypes } = {
  blocked_by: "blocking",
  blocking: "blocked_by",
  relates_to: "relates_to",
  duplicate: "duplicate",
  start_before: "start_after",
  start_after: "start_before",
  finish_before: "finish_after",
  finish_after: "finish_before",
};

// the relations the timeline draws as dependencies, named from either end
export const TIMELINE_DEPENDENCY_RELATIONS: TIssueRelationTypes[] = [
  "blocking",
  "blocked_by",
  "start_before",
  "start_after",
  "finish_before",
  "finish_after",
];
