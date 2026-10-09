/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable } from "mobx";
import { computedFn } from "mobx-utils";

export interface IIssueListViewStore {
  collapsedIssueIds: string[];
  // a work item has a row in every group it belongs to, so the selected row names its group too;
  // isEditing: its title is an input
  selectedRow: { issueId: string; groupId: string; isEditing?: boolean } | undefined;
  // computed
  getIsRowSelected: (issueId: string, groupId: string) => boolean;
  getIsRowTitleEdited: (issueId: string, groupId: string) => boolean;
  // actions
  toggleIssueCollapse: (issueId: string) => void;
  setSelectedRow: (row: IIssueListViewStore["selectedRow"]) => void;
}

export class IssueListViewStore implements IIssueListViewStore {
  collapsedIssueIds: string[] = [];
  selectedRow: IIssueListViewStore["selectedRow"] = undefined;

  constructor() {
    makeObservable(this, {
      collapsedIssueIds: observable,
      selectedRow: observable.ref,
      // actions
      toggleIssueCollapse: action,
      setSelectedRow: action,
    });
  }

  getIsRowSelected = computedFn(
    (issueId: string, groupId: string) => this.selectedRow?.issueId === issueId && this.selectedRow.groupId === groupId
  );

  getIsRowTitleEdited = computedFn(
    (issueId: string, groupId: string) => this.getIsRowSelected(issueId, groupId) && !!this.selectedRow?.isEditing
  );

  toggleIssueCollapse = (issueId: string) => {
    this.collapsedIssueIds = this.collapsedIssueIds.includes(issueId)
      ? this.collapsedIssueIds.filter((id) => id !== issueId)
      : [...this.collapsedIssueIds, issueId];
  };

  setSelectedRow = (row: IIssueListViewStore["selectedRow"]) => {
    this.selectedRow = row;
  };
}
