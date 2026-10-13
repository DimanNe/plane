/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { difference } from "lodash-es";
import type { TGroupedIssues } from "@plane/types";

export type TLineGroupChange = { issueId: string; groupId: string; newGroupId: string };

/** The groups of the list in which each work item has a line. */
const getGroupIdsOfWorkItems = (groupedIssueIds: TGroupedIssues) => {
  const groupIds: Record<string, string[]> = {};
  for (const [groupId, issueIds] of Object.entries(groupedIssueIds))
    for (const issueId of issueIds) (groupIds[issueId] ??= []).push(groupId);
  return groupIds;
};

/**
 * The lines of a grouped list that went from one group to another between two states of the list. A work item
 * with several labels has a line in the group of each, so its groups do not tell which line is meant unless it
 * has left exactly one group and entered exactly one: a label more is a line more, and no line has moved.
 */
export const getLinesGoneToAnotherGroup = (
  groupedIssueIdsBefore: TGroupedIssues,
  groupedIssueIds: TGroupedIssues
): TLineGroupChange[] => {
  const groupIdsBefore = getGroupIdsOfWorkItems(groupedIssueIdsBefore);
  return Object.entries(getGroupIdsOfWorkItems(groupedIssueIds)).flatMap(([issueId, groupIds]) => {
    const groupIdsLeft = difference(groupIdsBefore[issueId], groupIds);
    const groupIdsEntered = difference(groupIds, groupIdsBefore[issueId]);
    return groupIdsLeft.length === 1 && groupIdsEntered.length === 1
      ? [{ issueId, groupId: groupIdsLeft[0], newGroupId: groupIdsEntered[0] }]
      : [];
  });
};
