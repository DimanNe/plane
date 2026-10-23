/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
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
 * default state of the project. It is the same for the dialog that the "+" of the group opens and for the dialog
 * that is opened while a line of the group is selected.
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
 * The data of the group that a new work item is made in, for the dialog that makes it: the group whose "+" opened
 * the dialog, or else the group of the selected line of the List layout. The groups are read while the dialog is
 * open only, so that a move of the selection draws nothing of a closed dialog again.
 */
export const useNewWorkItemDataOfGroup = () => {
  // store hooks
  const { isCreateIssueModalOpen } = useCommandPalette();
  const listView = useListView();
  const { projectStates } = useProjectState();
  const { issuesFilter } = useIssuesStore();
  // A "+" chooses the group of one dialog only: the dialog that N I opens later takes the group of the selected
  // line again.
  useEffect(() => {
    if (!isCreateIssueModalOpen) listView.setGroupIdOfNewWorkItem(undefined);
  }, [isCreateIssueModalOpen, listView]);
  // derived values
  const groupId = isCreateIssueModalOpen ? (listView.groupIdOfNewWorkItem ?? listView.selectedRow?.groupId) : undefined;

  // in no group: a line of a list that is not grouped, and a line of the timeline
  if (!groupId || groupId === ALL_ISSUES) return undefined;
  return getWorkItemDataOfGroup(
    issuesFilter?.issueFilters?.displayFilters?.group_by ?? null,
    groupId,
    projectStates?.find((state) => state.default)?.id
  );
};
