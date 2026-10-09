/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { extractInstruction } from "@atlaskit/pragmatic-drag-and-drop-hitbox/tree-item";
import type { IPragmaticDropPayload, TIssueMap } from "@plane/types";
import type { GroupDropLocation } from "../utils";
import { getDestinationFromDropPayload } from "../utils";

// pixels: the indentation of a nesting level, and the space above a row for each level counted in `spacingLevel`
export const LIST_ROW_INDENT = 24;
export const LIST_ROW_SPACING = 12;

export type TListRow = {
  issueId: string;
  nestingLevel: number;
  hasSubIssues: boolean;
  isExpanded: boolean;
  // the greatest number of levels shown under the work item or under one of its siblings
  spacingLevel: number;
};

/**
 * The work items of a list group in the order of their rows: a work item whose parent is in the
 * same group follows that parent, one level deeper; the others stand at the top level.
 */
export const getListRows = (issueIds: string[], issuesMap: TIssueMap, collapsedIssueIds: string[]): TListRow[] => {
  const groupIssueIds = new Set(issueIds);
  const subIssueIds: Record<string, string[]> = {};
  const topLevelIssueIds: string[] = [];
  for (const issueId of issueIds) {
    const parentId = issuesMap[issueId]?.parent_id;
    if (parentId && groupIssueIds.has(parentId)) (subIssueIds[parentId] ??= []).push(issueId);
    else topLevelIssueIds.push(issueId);
  }

  const isExpanded = (issueId: string) => !!subIssueIds[issueId] && !collapsedIssueIds.includes(issueId);
  const getLevelsBelow = (issueId: string): number =>
    isExpanded(issueId) ? 1 + Math.max(...subIssueIds[issueId].map(getLevelsBelow)) : 0;

  const rows: TListRow[] = [];
  const addRows = (siblingIds: string[], nestingLevel: number) => {
    const spacingLevel = Math.max(...siblingIds.map(getLevelsBelow));
    for (const issueId of siblingIds) {
      rows.push({
        issueId,
        nestingLevel,
        hasSubIssues: !!subIssueIds[issueId],
        isExpanded: isExpanded(issueId),
        spacingLevel: rows.length > 0 ? spacingLevel : 0,
      });
      if (isExpanded(issueId)) addRows(subIssueIds[issueId], nestingLevel + 1);
    }
  };
  addRows(topLevelIssueIds, 0);
  return rows;
};

/**
 * Whether the work item is `parentId` itself or is under it, at any depth.
 * The API accepts a parent that is under its own sub-work item, so a work item is looked at once.
 */
export const isSubIssueOf = (issuesMap: TIssueMap, issueId: string, parentId: string) => {
  const visitedIssueIds = new Set<string>();
  let currentId: string | null | undefined = issueId;
  while (currentId && !visitedIssueIds.has(currentId)) {
    if (currentId === parentId) return true;
    visitedIssueIds.add(currentId);
    currentId = issuesMap[currentId]?.parent_id;
  }
  return false;
};

/**
 * Where a work item dropped in a list group goes: its parent, and the work item of the group it is placed before.
 * On a row it becomes the first sub-work item of that row; above or below a row, a sibling of that row; elsewhere
 * in the group it goes to the end of the top level. At the top level it keeps a parent that is outside the group.
 * Nothing is returned for a drop on the work item itself or on one of its sub-work items.
 */
export const getListDropLocation = (
  payload: IPragmaticDropPayload,
  issueIds: string[],
  issuesMap: TIssueMap
): GroupDropLocation | undefined => {
  const destination = getDestinationFromDropPayload(payload);
  const rowData = payload.location.current.dropTargets.find((dropTarget) => dropTarget.data.type === "ISSUE")?.data;
  const instruction = rowData && extractInstruction(rowData)?.type;
  if (!destination || instruction === "instruction-blocked") return;

  if (destination.id && instruction === "make-child")
    return {
      ...destination,
      id: issueIds.find((issueId) => issuesMap[issueId]?.parent_id === destination.id),
      parentId: destination.id,
    };

  const isInGroup = (issueId: string | null | undefined) => !!issueId && issueIds.includes(issueId);
  const rowParentId = destination.id && issuesMap[destination.id]?.parent_id;
  const sourceParentId = issuesMap[payload.source.data.id as string]?.parent_id;
  const parentId = isInGroup(rowParentId) ? rowParentId : isInGroup(sourceParentId) ? null : undefined;
  const nextIssueId = destination.id && issueIds[issueIds.indexOf(destination.id) + 1];
  if (instruction === "reorder-below" && nextIssueId)
    return { ...destination, id: nextIssueId, canAddIssueBelow: false, parentId };
  return { ...destination, parentId };
};
