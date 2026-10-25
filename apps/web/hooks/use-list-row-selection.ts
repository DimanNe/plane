/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef } from "react";
import { useParams } from "next/navigation";
// plane imports
import { useLatestCallback } from "@plane/hooks";
import type {
  IGroupByColumn,
  TGroupedIssues,
  TIssueGroupByOptions,
  TIssueKanbanFilters,
  TIssueMap,
} from "@plane/types";
// components
import { isListKey, isPressedInList } from "@/components/issues/issue-layouts/list/list-keys";
import type { TListRow } from "@/components/issues/issue-layouts/list/utils";
import { getIssueIdsOfList, getListRows } from "@/components/issues/issue-layouts/list/utils";
import { getIssueBlockId } from "@/components/issues/issue-layouts/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";
import useKeypress from "@/hooks/use-keypress";
import { useListRowDelete } from "@/hooks/use-list-row-delete";
import { useListRowEdit } from "@/hooks/use-list-row-edit";

type Props = {
  containerRef: React.MutableRefObject<HTMLElement | null>;
  groups: IGroupByColumn[] | undefined;
  groupedIssueIds: TGroupedIssues;
  issuesMap: TIssueMap;
  group_by: TIssueGroupByOptions | null;
  collapsedGroups: TIssueKanbanFilters;
};

const isPlainKey = (e: KeyboardEvent) => !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey;

/**
 * The selected row of the List layout: moved and opened with the keyboard, kept among the rows the list shows.
 * A component that uses it draws again at every move of the selection; see ListRowSelection.
 */
export const useListRowSelection = (props: Props) => {
  const { containerRef, groups = [], groupedIssueIds, issuesMap, group_by, collapsedGroups } = props;
  // router
  const { workspaceSlug } = useParams();
  // store hooks
  const { collapsedIssueIds, selectedRow, setSelectedRow, toggleIssueCollapse, isSelectionLeftAtPlaceOf } =
    useListView();
  const { peekIssue, setPeekIssue } = useIssueDetail();

  // the rows in the order the list shows them, but for those of work items in another group, which only show the
  // structure there
  const issueIdsOfList = getIssueIdsOfList(groupedIssueIds);
  const rows = groups.flatMap((group) =>
    group_by && collapsedGroups.group_by.includes(group.id)
      ? []
      : getListRows(groupedIssueIds[group.id] ?? [], issuesMap, collapsedIssueIds, issueIdsOfList)
          .filter((row) => !row.isInAnotherGroup)
          .map((row) => Object.assign(row, { groupId: group.id }))
  );
  const selectedRowIndex = rows.findIndex(
    (row) => row.issueId === selectedRow?.issueId && row.groupId === selectedRow.groupId
  );
  const selectedIssueGroupId = rows.find((row) => row.issueId === selectedRow?.issueId)?.groupId;

  const { getRowInPlaceOf, getRowAtSelectedPlace } = useListRowDelete({
    containerRef,
    rows,
    selectedRowIndex,
    issuesMap,
  });
  // the work item view beside the list shows the row that took the place of the one it showed
  const openRowInPlaceOf = useLatestCallback((issueId: string, row: TListRow) => {
    if (peekIssue?.issueId === issueId) openRow(row);
  });

  // A selected work item that moved to another group stays selected there, one that left the list is dropped.
  // One that the Delete key removed leaves the selection to the row that took its place, so that the arrow keys
  // go on from there. So does one that the state keys sent to another group: S and a letter, pressed again, then
  // work down the group it left. Where no other row is, the selection stays with it.
  useEffect(() => {
    if (!selectedRow || selectedRowIndex !== -1) return;
    if (selectedIssueGroupId) {
      const rowInPlace = isSelectionLeftAtPlaceOf(selectedRow.issueId)
        ? getRowAtSelectedPlace(selectedRow.issueId)
        : undefined;
      setSelectedRow({
        issueId: rowInPlace?.issueId ?? selectedRow.issueId,
        groupId: rowInPlace?.groupId ?? selectedIssueGroupId,
      });
      return;
    }
    const rowInPlace = getRowInPlaceOf(selectedRow.issueId);
    setSelectedRow(rowInPlace && { issueId: rowInPlace.issueId, groupId: rowInPlace.groupId });
    if (rowInPlace) openRowInPlaceOf(selectedRow.issueId, rowInPlace);
  }, [
    selectedRow,
    selectedRowIndex,
    selectedIssueGroupId,
    setSelectedRow,
    getRowInPlaceOf,
    getRowAtSelectedPlace,
    isSelectionLeftAtPlaceOf,
    openRowInPlaceOf,
  ]);

  // without a list nothing is selected
  useEffect(() => () => setSelectedRow(undefined), [setSelectedRow]);

  const openRow = (row: TListRow) => {
    const issue = issuesMap[row.issueId];
    if (!workspaceSlug || !issue?.project_id) return;
    setPeekIssue({
      workspaceSlug: workspaceSlug.toString(),
      projectId: issue.project_id,
      issueId: issue.id,
      nestingLevel: row.nestingLevel,
      isArchived: !!issue.archived_at,
    });
  };

  // The rows on either side of the last click in the list. With no row selected the arrow keys start there, at what
  // the person was looking at, rather than at the top of the list: after a click on the header of an empty group,
  // Arrow Down selects the first row below it, in the next group that has one.
  const rowsAroundLastClickRef = useRef<{ below?: (typeof rows)[number]; above?: (typeof rows)[number] }>({});
  const keepRowsAroundLastClick = useLatestCallback((e: PointerEvent) => {
    if (!(e.target instanceof Element) || !containerRef.current?.contains(e.target)) return;
    const rowsAroundClick: typeof rowsAroundLastClickRef.current = {};
    for (const row of rows) {
      // a row that is not drawn, far from the click, has no place to compare
      const place = document.getElementById(getIssueBlockId(row.issueId, row.groupId))?.getBoundingClientRect();
      if (!place) continue;
      // a row under the click is on both sides of it
      if (place.top < e.clientY) rowsAroundClick.above = row;
      if (place.bottom > e.clientY) rowsAroundClick.below ??= row;
    }
    rowsAroundLastClickRef.current = rowsAroundClick;
  });
  useEffect(() => {
    document.addEventListener("pointerdown", keepRowsAroundLastClick, true);
    return () => document.removeEventListener("pointerdown", keepRowsAroundLastClick, true);
  }, [keepRowsAroundLastClick]);

  /** The row that an arrow key selects where none is: the one beside the last click that the key goes towards. */
  const getRowBesideLastClick = (step: number) => {
    const { below, above } = rowsAroundLastClickRef.current;
    const besideClick = step > 0 ? (below ?? above) : (above ?? below);
    return (
      (besideClick && rows.find((row) => row.issueId === besideClick.issueId && row.groupId === besideClick.groupId)) ??
      rows[0]
    );
  };

  // A click on a control of a row (its state, "Add child", a right click for its menu) selects the row too, so that
  // the keys then act on the work item the person was busy with. The controls keep their clicks from the row, whose
  // own click would open the work item, so the row's handler never hears of them.
  // FOR_REVIEWER: the owner approved this rule while the pointer still selected the row on its way to the control.
  // A drag, which ends without a click, selects nothing; nor does a Ctrl or Cmd click, which opens the work item in
  // another tab and leaves this one, its address included, as it was. The address follows this selection as it
  // follows every other, so a reload after such a click opens the work item beside the list (list/state_circle,
  // list/filter_from_line). While the pointer selected, the address stayed with the row before; keeping that for a
  // click on a control would take a second kind of selection again.
  const selectClickedRow = useLatestCallback((e: MouseEvent) => {
    if (e.type === "click" && (e.ctrlKey || e.metaKey)) return;
    if (!(e.target instanceof Element) || !containerRef.current?.contains(e.target)) return;
    const rowElement = e.target.closest('[id^="issue_"]');
    // a row of a work item in another group, which only shows the structure, is not among the rows
    const clickedRow = rowElement && rows.find((row) => getIssueBlockId(row.issueId, row.groupId) === rowElement.id);
    if (!clickedRow || (clickedRow.issueId === selectedRow?.issueId && clickedRow.groupId === selectedRow.groupId))
      return;
    setSelectedRow({ issueId: clickedRow.issueId, groupId: clickedRow.groupId });
  });
  useEffect(() => {
    document.addEventListener("click", selectClickedRow, true);
    document.addEventListener("contextmenu", selectClickedRow, true);
    return () => {
      document.removeEventListener("click", selectClickedRow, true);
      document.removeEventListener("contextmenu", selectClickedRow, true);
    };
  }, [selectClickedRow]);

  // While an arrow key is held the work item view beside the list does not follow the selection, and shows the row
  // the selection stops on when the key is released. Only the release of such a key does that: an arrow key released
  // in the title or the description of the work item in the view moved nothing of the list, and the view may show
  // another work item than the selected row, such as a sub-work item opened from within it.
  const isViewWaitingForKeyUpRef = useRef(false);
  const moveSelection = (e: KeyboardEvent, step: number) => {
    // the arrow keys also leave the title of the selected row while it is edited, a field of the list
    const isInEditedTitle = !!selectedRow?.isEditing && !e.defaultPrevented && isPressedInList(e, containerRef.current);
    if (!isPlainKey(e) || !(isListKey(e, containerRef.current) || isInEditedTitle)) return;
    e.preventDefault();
    const row = selectedRow ? rows[selectedRowIndex + step] : getRowBesideLastClick(step);
    if (!row) return;
    // the input of an edited title saves the name as the focus leaves it
    if (selectedRow?.isEditing && document.activeElement instanceof HTMLElement) document.activeElement.blur();
    setSelectedRow({ issueId: row.issueId, groupId: row.groupId });
    const rowElement = document.getElementById(getIssueBlockId(row.issueId, row.groupId));
    rowElement?.scrollIntoView({ block: "nearest" });
    // the focus goes with the selection, as it does on a click
    rowElement?.querySelector("a")?.focus({ preventScroll: true });
    // The work item view beside the list shows the selected work item. A held key passes many rows, and each
    // one shown would load its work item, so the view waits for the row the selection stops on.
    if (peekIssue && !e.repeat) openRow(row);
    isViewWaitingForKeyUpRef.current = !!peekIssue && e.repeat;
  };

  const showSelectedRowAfterHeldKey = useLatestCallback((e: KeyboardEvent) => {
    if ((e.key !== "ArrowDown" && e.key !== "ArrowUp") || !isViewWaitingForKeyUpRef.current) return;
    isViewWaitingForKeyUpRef.current = false;
    const row = rows[selectedRowIndex];
    if (!row || !peekIssue || peekIssue.issueId === row.issueId) return;
    openRow(row);
  });
  useEffect(() => {
    document.addEventListener("keyup", showSelectedRowAfterHeldKey);
    return () => document.removeEventListener("keyup", showSelectedRowAfterHeldKey);
  }, [showSelectedRowAfterHeldKey]);

  const toggleSelectedRow = (e: KeyboardEvent, shouldExpand: boolean) => {
    const row = rows[selectedRowIndex];
    if (!isPlainKey(e) || !isListKey(e, containerRef.current) || !row?.hasSubIssues || row.isExpanded === shouldExpand)
      return;
    e.preventDefault();
    toggleIssueCollapse(row.issueId);
  };

  useListRowEdit({ containerRef, selectedRow: rows[selectedRowIndex], openRow });
  useKeypress("ArrowDown", (e) => moveSelection(e, 1));
  useKeypress("ArrowUp", (e) => moveSelection(e, -1));
  useKeypress("ArrowRight", (e) => toggleSelectedRow(e, true));
  useKeypress("ArrowLeft", (e) => toggleSelectedRow(e, false));
  useKeypress("Enter", (e) => {
    const row = rows[selectedRowIndex];
    // Enter on a button, or on a link outside the list, activates that
    const isOnRow = e.target instanceof HTMLAnchorElement && containerRef.current?.contains(e.target);
    if (!isPlainKey(e) || !isListKey(e, containerRef.current) || !row || !(e.target === document.body || isOnRow))
      return;
    e.preventDefault();
    openRow(row);
  });
};
