/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IPragmaticDropPayload, TGroupedIssues, TIssueMap } from "@plane/types";
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
  // The work item is in another group of the list. Its row stands here only to show the parent of the rows under
  // it, and nothing done in this group changes it.
  isInAnotherGroup: boolean;
};

/** The work items of all the groups of a list, which a group shows as parents of its own. */
export const getIssueIdsOfList = (groupedIssueIds: TGroupedIssues) => new Set(Object.values(groupedIssueIds).flat());

/**
 * The work items that the rows of a list group show: those of the group and, before a work item, the parents of it
 * that the list shows in other groups, so that the group shows the structure of its work items wherever they are.
 * A parent that the list does not show, as when a filter hides it, ends the chain.
 */
const getIssueIdsShownInGroup = (issueIds: string[], issuesMap: TIssueMap, issueIdsOfList: Set<string>) => {
  const groupIssueIds = new Set(issueIds);
  const issueIdsInAnotherGroup = new Set<string>();
  const shownIssueIds: string[] = [];
  for (const issueId of issueIds) {
    const parentIds: string[] = [];
    // the API accepts a parent that is under its own sub-work item, so a work item is looked at once
    const visitedIssueIds = new Set([issueId]);
    let parentId = issuesMap[issueId]?.parent_id;
    while (
      parentId &&
      issueIdsOfList.has(parentId) &&
      !groupIssueIds.has(parentId) &&
      !issueIdsInAnotherGroup.has(parentId) &&
      !visitedIssueIds.has(parentId)
    ) {
      parentIds.unshift(parentId);
      visitedIssueIds.add(parentId);
      parentId = issuesMap[parentId]?.parent_id;
    }
    for (const id of parentIds) issueIdsInAnotherGroup.add(id);
    shownIssueIds.push(...parentIds, issueId);
  }
  return { shownIssueIds, issueIdsInAnotherGroup };
};

/**
 * The rows of a list group in their order: a work item whose parent is shown in the group follows that parent,
 * one level deeper; the others stand at the top level. `issueIdsOfList` are the work items of all the groups.
 */
export const getListRows = (
  issueIds: string[],
  issuesMap: TIssueMap,
  collapsedIssueIds: string[],
  issueIdsOfList: Set<string>
): TListRow[] => {
  const { shownIssueIds, issueIdsInAnotherGroup } = getIssueIdsShownInGroup(issueIds, issuesMap, issueIdsOfList);
  const shownIssueIdSet = new Set(shownIssueIds);
  const subIssueIds: Record<string, string[]> = {};
  const topLevelIssueIds: string[] = [];
  for (const issueId of shownIssueIds) {
    const parentId = issuesMap[issueId]?.parent_id;
    if (parentId && shownIssueIdSet.has(parentId)) (subIssueIds[parentId] ??= []).push(issueId);
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
        isInAnotherGroup: issueIdsInAnotherGroup.has(issueId),
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
 * The sub-work items that the row of a work item takes with it in a drop into another group: the rows under it in
 * its group, folded or not. What is seen to go is what changes. A sub-work item in another group stays there, and so
 * does a parent in another group whose row only shows the structure here.
 */
export const getCarriedSubIssueIds = (
  issueId: string,
  issueIds: string[],
  issuesMap: TIssueMap,
  issueIdsOfList: Set<string>
): string[] => {
  // FOR_REVIEWER: open question, decided this way: a sub-work item that is already in another group (a done one
  // under a parent to do) has no row under the dragged one, so it stays where it is. The alternative is to give
  // every sub-work item the new value, which would also undo a sub-work item that was done.
  const rows = getListRows(issueIds, issuesMap, [], issueIdsOfList);
  const index = rows.findIndex((row) => row.issueId === issueId);
  if (index === -1) return [];
  const carriedSubIssueIds: string[] = [];
  for (const row of rows.slice(index + 1)) {
    if (row.nestingLevel <= rows[index].nestingLevel) break;
    if (!row.isInAnotherGroup) carriedSubIssueIds.push(row.issueId);
  }
  return carriedSubIssueIds;
};

/**
 * Where a work item dropped in a list group goes, and the row that the list marks for it: its parent, and the work
 * item of the group it is placed before. A drop on a row makes that row its parent, and it goes as the first of its
 * sub-work items. What any other drop does depends on where the drag began:
 * - A drop within the group edits the structure. Above or below a row the work item becomes a sibling of that row,
 *   under the row's parent; at the top level it has no parent, also where its parent is shown from another group.
 * - A drop into another group changes the work item's value and keeps its parent. Above or below a sibling it takes
 *   that place. Anywhere else it goes under its parent where the group shows it, as the first of its sub-work items,
 *   and to the end of the top level where the group does not.
 * Nothing is returned for a drop on the work item itself or on one of its sub-work items.
 */
const getListDrop = (
  payload: IPragmaticDropPayload,
  issueIds: string[],
  issuesMap: TIssueMap,
  issueIdsOfList: Set<string>
): { location: GroupDropLocation; markedRow?: { id: string; place: TListRowDropPlace } } | undefined => {
  const destination = getDestinationFromDropPayload(payload);
  const row = getRowDropData(payload);
  if (!destination || (row && !row.place)) return;

  const getDropInto = (parentId: string, isParentNew: boolean) => ({
    location: {
      ...destination,
      id: issueIds.find((issueId) => issuesMap[issueId]?.parent_id === parentId),
      parentId: isParentNew ? parentId : undefined,
    },
    markedRow: { id: parentId, place: "inside" as const },
  });
  if (destination.id && row?.place === "inside") return getDropInto(destination.id, true);

  const { shownIssueIds } = getIssueIdsShownInGroup(issueIds, issuesMap, issueIdsOfList);
  // the parent under which the group shows a work item; null at the top level
  const getShownParentId = (issueId: string) => {
    const parentId = issuesMap[issueId]?.parent_id;
    return parentId && shownIssueIds.includes(parentId) ? parentId : null;
  };
  const getDropBesideRow = (parentId: string | null | undefined) => {
    const markedRow = destination.id && row?.place ? { id: destination.id, place: row.place } : undefined;
    const nextIssueId = destination.id && issueIds[issueIds.indexOf(destination.id) + 1];
    if (row?.place === "below" && nextIssueId)
      return { location: { ...destination, id: nextIssueId, canAddIssueBelow: false, parentId }, markedRow };
    return { location: { ...destination, canAddIssueBelow: row?.place === "below", parentId }, markedRow };
  };
  const sourceId = payload.source.data.id as string;
  const sourceParentId = getShownParentId(sourceId);
  const rowParentId = destination.id ? getShownParentId(destination.id) : null;

  const isDropWithinGroup = payload.source.data.groupId === destination.groupId;
  // FOR_REVIEWER: open question, decided this way: at the top level a drop within the group takes away a parent that
  // the group shows, and keeps one that it does not (a filter hides it): the work item already stands at the top
  // level there, and a drop that only moves it among its siblings changes nothing else.
  if (isDropWithinGroup) return getDropBesideRow(rowParentId ?? (sourceParentId ? null : undefined));

  if (destination.id && row?.place && rowParentId === sourceParentId) return getDropBesideRow(undefined);
  if (sourceParentId) return getDropInto(sourceParentId, false);
  return { location: { ...destination, id: undefined, canAddIssueBelow: false } };
};

export const getListDropLocation = (
  payload: IPragmaticDropPayload,
  issueIds: string[],
  issuesMap: TIssueMap,
  issueIdsOfList: Set<string>
): GroupDropLocation | undefined => getListDrop(payload, issueIds, issuesMap, issueIdsOfList)?.location;

/**
 * What the list draws for a row that is held over a group. It is made from where a drop would put the row, so
 * the picture cannot say one thing and the drop do another, and there is none where a drop does nothing.
 * At a row the place is the pointer's in every order of the list: a line above or below the row, or the row that
 * takes the held row in, which in a drop into another group can be the row of the held row's parent. An order other
 * than the manual one then puts the dropped row where it belongs, in the group and under the parent that the line
 * showed. Elsewhere in a group the group is marked, and in the manual order a line stands at its end, where the row
 * lands.
 */
export const getListDropMark = (
  payload: IPragmaticDropPayload,
  issueIds: string[],
  issuesMap: TIssueMap,
  issueIdsOfList: Set<string>,
  isManualOrder: boolean
): TListDropMark | undefined => {
  const drop = getListDrop(payload, issueIds, issuesMap, issueIdsOfList);
  if (!drop) return;
  return {
    groupId: drop.location.groupId,
    issueId: drop.markedRow?.id,
    place: drop.markedRow?.place ?? (isManualOrder ? "end" : "inside"),
  };
};
