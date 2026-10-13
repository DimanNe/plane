/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IPragmaticDropPayload, TIssueMap } from "@plane/types";
import type { TListDropMark } from "@/store/issue/issue_list_view.store";
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

type TListRowDropPlace = "above" | "below" | "inside";

/** What a row tells a row that is held over it: `place` is missing where a drop does nothing. */
export type TListRowDropData = { id: string; type: "ISSUE"; place?: TListRowDropPlace };

// the share of a row's height, from its upper and from its lower edge, where a held row goes above or below it
const ROW_EDGE_SHARE = 3 / 8;

/**
 * Where a row that is held over another row goes: above it, below it, or into it as a sub-work item. The edges
 * take most of the row, so that the line between two rows stays while the pointer is anywhere near it; the
 * middle is what is left for making a sub-work item. Below a row that shows its sub-work items is the place of
 * the first of them.
 */
export const getListRowDropPlace = (row: Element, pointerY: number, isExpanded: boolean): TListRowDropPlace => {
  const { top, height } = row.getBoundingClientRect();
  const share = (pointerY - top) / height;
  if (share < ROW_EDGE_SHARE) return "above";
  return share > 1 - ROW_EDGE_SHARE && !isExpanded ? "below" : "inside";
};

const getRowDropData = (payload: IPragmaticDropPayload) =>
  payload.location.current.dropTargets.find((dropTarget) => dropTarget.data.type === "ISSUE")?.data as
    | TListRowDropData
    | undefined;

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
  const row = getRowDropData(payload);
  if (!destination || (row && !row.place)) return;

  if (destination.id && row?.place === "inside")
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
  if (row?.place === "below" && nextIssueId)
    return { ...destination, id: nextIssueId, canAddIssueBelow: false, parentId };
  return { ...destination, canAddIssueBelow: row?.place === "below", parentId };
};

/**
 * What the list draws for a row that is held over a group. It is made from where a drop would put the row, so
 * the picture cannot say one thing and the drop do another, and there is none where a drop does nothing.
 * At a row the place is the pointer's in every order of the list: a line above or below the row, or the row that
 * takes the held row in. An order other than the manual one then puts the dropped row where it belongs, in the
 * group and under the parent that the line showed. Elsewhere in a group the group is marked, and in the manual
 * order a line stands at its end, where the row lands.
 */
export const getListDropMark = (
  payload: IPragmaticDropPayload,
  issueIds: string[],
  issuesMap: TIssueMap,
  isManualOrder: boolean
): TListDropMark | undefined => {
  const location = getListDropLocation(payload, issueIds, issuesMap);
  if (!location) return;
  const row = getRowDropData(payload);
  return { groupId: location.groupId, issueId: row?.id, place: row?.place ?? (isManualOrder ? "end" : "inside") };
};
