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
  // The work item whose description is to take the caret (the key E on its line). The view beside the list loads
  // the work item before it has an editor, and what is typed in between is the description's: it is kept here
  // and kept from the shortcuts of the page.
  descriptionAwaitingCaret: string | undefined;
  // computed
  getIsRowSelected: (issueId: string, groupId: string) => boolean;
  getIsRowTitleEdited: (issueId: string, groupId: string) => boolean;
  // actions
  toggleIssueCollapse: (issueId: string) => void;
  setSelectedRow: (row: IIssueListViewStore["selectedRow"]) => void;
  awaitDescriptionCaret: (issueId: string) => void;
  /** Ends the wait and returns what was typed during it. */
  takeTypedForDescription: () => string;
}

export class IssueListViewStore implements IIssueListViewStore {
  collapsedIssueIds: string[] = [];
  selectedRow: IIssueListViewStore["selectedRow"] = undefined;
  descriptionAwaitingCaret: string | undefined = undefined;
  private typedForDescription = "";

  constructor() {
    makeObservable(this, {
      collapsedIssueIds: observable,
      selectedRow: observable.ref,
      descriptionAwaitingCaret: observable,
      // actions
      toggleIssueCollapse: action,
      setSelectedRow: action,
      awaitDescriptionCaret: action,
      takeTypedForDescription: action,
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

  awaitDescriptionCaret = (issueId: string) => {
    this.descriptionAwaitingCaret = issueId;
    this.typedForDescription = "";
    document.addEventListener("keydown", this.holdKeyForDescription, true);
  };

  takeTypedForDescription = () => {
    document.removeEventListener("keydown", this.holdKeyForDescription, true);
    this.descriptionAwaitingCaret = undefined;
    return this.typedForDescription;
  };

  // Before everybody else on the page. Escape is left alone: it closes the view, which ends the wait. A key with
  // Ctrl, Cmd or Alt is not text.
  private holdKeyForDescription = (e: KeyboardEvent) => {
    if (e.key === "Escape" || e.ctrlKey || e.metaKey || e.altKey) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (e.key.length === 1) this.typedForDescription += e.key;
  };
}
