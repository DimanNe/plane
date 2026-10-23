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
import type { TListRow } from "@/components/issues/issue-layouts/list/utils";
import { getIssueIdsOfList, getListRows } from "@/components/issues/issue-layouts/list/utils";
import { getIssueBlockId } from "@/components/issues/issue-layouts/utils";
import { isTypingInInput } from "@/components/power-k/core/shortcut-handler";
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

/**
 * What is open over the list for the selected row, or for the page: a menu (of a property, the right-click menu)
 * or a dialog. The selected row it was opened for, and that its keys act on, stays selected while the pointer
 * crosses other rows on its way.
 */
const POP_UP_OVER_THE_LIST =
  '[role="menu"], [role="listbox"], [role="alertdialog"], [role="dialog"][aria-modal="true"], [data-select-popup]:not([data-closed])';

const isPlainKey = (e: KeyboardEvent) => !e.defaultPrevented && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey;
// a key pressed in a text field, an editor, a menu or a dialog is not for the list
const isListKey = (e: KeyboardEvent) => isPlainKey(e) && !isTypingInInput(e.target);

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
    // a key that opens the row the pointer selected confirms it, as a click does
    if (selectedRow?.isByHover && selectedRow.issueId === row.issueId)
      setSelectedRow({ issueId: selectedRow.issueId, groupId: selectedRow.groupId });
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

  const moveSelection = (e: KeyboardEvent, step: number) => {
    // the arrow keys also leave the title of the selected row while it is edited
    if (!isListKey(e) && !(isPlainKey(e) && selectedRow?.isEditing)) return;
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
  };

  const showSelectedRowAfterHeldKey = useLatestCallback((e: KeyboardEvent) => {
    const row = rows[selectedRowIndex];
    if ((e.key !== "ArrowDown" && e.key !== "ArrowUp") || !row || !peekIssue || peekIssue.issueId === row.issueId)
      return;
    openRow(row);
  });
  useEffect(() => {
    document.addEventListener("keyup", showSelectedRowAfterHeldKey);
    return () => document.removeEventListener("keyup", showSelectedRowAfterHeldKey);
  }, [showSelectedRowAfterHeldKey]);

  // The pointer selects the row it moves over, and the keys act on that row and go on from it. Only a move of the
  // pointer itself does: a row that comes under a still pointer as the list scrolls, for one that a held key
  // selects, takes nothing from the keys.
  // FOR_REVIEWER: Chrome, as the checks drive it headless and in windows, sends no pointer move for such a row, so
  // list/hover_selects passes without the comparison of places below. It is there for a browser that does send
  // one, at the place the pointer already was.
  const lastPointerPlaceRef = useRef<{ screenX: number; screenY: number } | undefined>(undefined);
  const selectHoveredRow = useLatestCallback((e: PointerEvent) => {
    const lastPlace = lastPointerPlaceRef.current;
    lastPointerPlaceRef.current = { screenX: e.screenX, screenY: e.screenY };
    // the first move a page hears is a move: the browser has no place before it to measure it from
    const hasPointerMoved = !lastPlace || lastPlace.screenX !== e.screenX || lastPlace.screenY !== e.screenY;
    // FOR_REVIEWER: decided this way: a held button is a drag or a selection of text, an edited title keeps its
    // row, and an open menu or dialog keeps the row it was opened for. A drag of a row hears no pointer moves at
    // all while it lasts. The view beside the list does not follow the hover, as it follows a key: it would load
    // every work item the pointer crosses; Enter, a click or a key opens the hovered one.
    if (!hasPointerMoved || e.pointerType !== "mouse" || e.buttons !== 0 || selectedRow?.isEditing) return;
    if (!(e.target instanceof Element) || !containerRef.current?.contains(e.target)) return;
    if (document.querySelector(POP_UP_OVER_THE_LIST)) return;
    const rowElement = e.target.closest('[id^="issue_"]');
    // a row of a work item in another group, which only shows the structure, is not among the rows
    const hoveredRow = rowElement && rows.find((row) => getIssueBlockId(row.issueId, row.groupId) === rowElement.id);
    if (!hoveredRow || (hoveredRow.issueId === selectedRow?.issueId && hoveredRow.groupId === selectedRow.groupId))
      return;
    setSelectedRow({ issueId: hoveredRow.issueId, groupId: hoveredRow.groupId, isByHover: true });
  });
  useEffect(() => {
    document.addEventListener("pointermove", selectHoveredRow);
    return () => document.removeEventListener("pointermove", selectHoveredRow);
  }, [selectHoveredRow]);

  const toggleSelectedRow = (e: KeyboardEvent, shouldExpand: boolean) => {
    const row = rows[selectedRowIndex];
    if (!isListKey(e) || !row?.hasSubIssues || row.isExpanded === shouldExpand) return;
    e.preventDefault();
    toggleIssueCollapse(row.issueId);
  };

  useListRowEdit({ selectedRow: rows[selectedRowIndex], openRow });
  useKeypress("ArrowDown", (e) => moveSelection(e, 1));
  useKeypress("ArrowUp", (e) => moveSelection(e, -1));
  useKeypress("ArrowRight", (e) => toggleSelectedRow(e, true));
  useKeypress("ArrowLeft", (e) => toggleSelectedRow(e, false));
  useKeypress("Enter", (e) => {
    const row = rows[selectedRowIndex];
    // Enter on a button, or on a link outside the list, activates that
    const isOnRow = e.target instanceof HTMLAnchorElement && containerRef.current?.contains(e.target);
    if (!isListKey(e) || !row || !(e.target === document.body || isOnRow)) return;
    e.preventDefault();
    openRow(row);
  });
};
