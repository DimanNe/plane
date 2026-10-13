/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { ALL_ISSUES } from "@plane/constants";
import type { TIssue } from "@plane/types";
// hooks
import { useCommandPalette } from "@/hooks/store/use-command-palette";
import { useListView } from "@/hooks/store/use-list-view";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useIssuesStore } from "@/hooks/use-issue-layout-store";

/**
 * What a new work item takes from the group of the list it is made in: the value the group stands for, and the
 * default state of the project. It is the same for the "+" of a group and for the dialog that is opened while a
 * line of the group is selected.
 */
export const getWorkItemDataOfGroup = (
  groupByKey: string | null,
  value: any,
  defaultStateId: string | undefined
): Partial<TIssue> => {
  let preloadedData: Partial<TIssue> = { state_id: defaultStateId };

  if (groupByKey === null) {
    preloadedData = { ...preloadedData };
  } else {
    if (groupByKey === "state") {
      preloadedData = { ...preloadedData, state_id: value };
    } else if (groupByKey === "priority") {
      preloadedData = { ...preloadedData, priority: value };
    } else if (groupByKey === "labels" && value != "None") {
      preloadedData = { ...preloadedData, label_ids: [value] };
    } else if (groupByKey === "assignees" && value != "None") {
      preloadedData = { ...preloadedData, assignee_ids: [value] };
    } else if (groupByKey === "cycle" && value != "None") {
      preloadedData = { ...preloadedData, cycle_id: value };
    } else if (groupByKey === "module" && value != "None") {
      preloadedData = { ...preloadedData, module_ids: [value] };
    } else if (groupByKey === "milestone") {
      preloadedData = { ...preloadedData, milestone_id: value === "None" ? null : value };
    } else if (groupByKey === "created_by") {
      preloadedData = { ...preloadedData };
    } else {
      preloadedData = { ...preloadedData, [groupByKey]: value };
    }
  }

  return preloadedData;
};

/**
 * The data of the group of the selected line of the List layout, for the dialog that makes a new work item. The
 * selection is read while the dialog is open only, so that a move of the selection draws nothing of a closed
 * dialog again.
 */
export const useNewWorkItemDataOfSelectedGroup = () => {
  // store hooks
  const { isCreateIssueModalOpen } = useCommandPalette();
  const listView = useListView();
  const { projectStates } = useProjectState();
  const { issuesFilter } = useIssuesStore();
  // derived values
  const selectedRow = isCreateIssueModalOpen ? listView.selectedRow : undefined;

  // in no group: a line of a list that is not grouped, and a line of the timeline
  if (!selectedRow || selectedRow.groupId === ALL_ISSUES) return undefined;
  return getWorkItemDataOfGroup(
    issuesFilter?.issueFilters?.displayFilters?.group_by ?? null,
    selectedRow.groupId,
    projectStates?.find((state) => state.default)?.id
  );
};
