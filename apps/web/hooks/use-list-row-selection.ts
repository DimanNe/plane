/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
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
import { getListRows } from "@/components/issues/issue-layouts/list/utils";
import { getIssueBlockId } from "@/components/issues/issue-layouts/utils";
import { isTypingInInput } from "@/components/power-k/core/shortcut-handler";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";
import useKeypress from "@/hooks/use-keypress";

type Props = {
  containerRef: React.MutableRefObject<HTMLElement | null>;
  groups: IGroupByColumn[] | undefined;
  groupedIssueIds: TGroupedIssues;
  issuesMap: TIssueMap;
  group_by: TIssueGroupByOptions | null;
  collapsedGroups: TIssueKanbanFilters;
};

const isPlainKey = (e: KeyboardEvent) => !e.defaultPrevented && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey;
// a key pressed in a text field, an editor, a menu or a dialog is not for the list
const isListKey = (e: KeyboardEvent) => isPlainKey(e) && !isTypingInInput(e.target);

/**
 * The selected row of the List layout: moved and opened with the keyboard, kept among the rows the list shows
 */
export const useListRowSelection = (props: Props) => {
  const { containerRef, groups = [], groupedIssueIds, issuesMap, group_by, collapsedGroups } = props;
  // router
  const { workspaceSlug } = useParams();
  // store hooks
  const { collapsedIssueIds, selectedRow, setSelectedRow, toggleIssueCollapse } = useListView();
  const { peekIssue, setPeekIssue } = useIssueDetail();

  // the rows in the order the list shows them
  const rows = groups.flatMap((group) =>
    group_by && collapsedGroups.group_by.includes(group.id)
      ? []
      : getListRows(groupedIssueIds[group.id] ?? [], issuesMap, collapsedIssueIds).map((row) =>
          Object.assign(row, { groupId: group.id })
        )
  );
  const selectedRowIndex = rows.findIndex(
    (row) => row.issueId === selectedRow?.issueId && row.groupId === selectedRow.groupId
  );
  const selectedIssueGroupId = rows.find((row) => row.issueId === selectedRow?.issueId)?.groupId;

  // a selected work item that moved to another group stays selected there, one that left the list is dropped
  useEffect(() => {
    if (!selectedRow || selectedRowIndex !== -1) return;
    setSelectedRow(selectedIssueGroupId ? { issueId: selectedRow.issueId, groupId: selectedIssueGroupId } : undefined);
  }, [selectedRow, selectedRowIndex, selectedIssueGroupId, setSelectedRow]);

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

  const moveSelection = (e: KeyboardEvent, step: number) => {
    // the arrow keys also leave the title of the selected row while it is edited
    if (!isListKey(e) && !(isPlainKey(e) && selectedRow?.isEditing)) return;
    e.preventDefault();
    const row = selectedRow ? rows[selectedRowIndex + step] : rows[0];
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

  const toggleSelectedRow = (e: KeyboardEvent, shouldExpand: boolean) => {
    const row = rows[selectedRowIndex];
    if (!isListKey(e) || !row?.hasSubIssues || row.isExpanded === shouldExpand) return;
    e.preventDefault();
    toggleIssueCollapse(row.issueId);
  };

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
