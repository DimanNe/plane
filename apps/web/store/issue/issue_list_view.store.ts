/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable } from "mobx";
import { computedFn } from "mobx-utils";

/**
 * What the list draws for the row that is held over it, which is where a drop would put that row. With a row: a
 * line above or below it, or the row marked as the one that takes the dropped row in. Without a row the group is
 * marked, and at "end" a line stands under its last row.
 */
export type TListDropMark = { groupId: string; issueId?: string; place: "above" | "below" | "inside" | "end" };

export interface IIssueListViewStore {
  collapsedIssueIds: string[];
  // a work item has a row in every group it belongs to, so the selected row names its group too;
  // isEditing: its title is an input
  selectedRow: { issueId: string; groupId: string; isEditing?: boolean } | undefined;
  // The work item whose description is to take the caret (the key E on its line). The view beside the list loads
  // the work item before it has an editor, and what is typed in between is the description's: it is kept here
  // and kept from the shortcuts of the page.
  descriptionAwaitingCaret: string | undefined;
  dropMark: TListDropMark | undefined;
  // computed
  getIsRowSelected: (issueId: string, groupId: string) => boolean;
  getIsRowTitleEdited: (issueId: string, groupId: string) => boolean;
  getRowDropPlace: (issueId: string, groupId: string) => TListDropMark["place"] | undefined;
  getGroupDropPlace: (groupId: string) => TListDropMark["place"] | undefined;
  // actions
  toggleIssueCollapse: (issueId: string) => void;
  setSelectedRow: (row: IIssueListViewStore["selectedRow"]) => void;
  awaitDescriptionCaret: (issueId: string) => void;
  /** Ends the wait and returns what was typed during it. */
  takeTypedForDescription: () => string;
  setDropMark: (mark: TListDropMark | undefined) => void;
}

export class IssueListViewStore implements IIssueListViewStore {
  collapsedIssueIds: string[] = [];
  selectedRow: IIssueListViewStore["selectedRow"] = undefined;
  descriptionAwaitingCaret: string | undefined = undefined;
  private typedForDescription = "";
  dropMark: TListDropMark | undefined = undefined;

  constructor() {
    makeObservable(this, {
      collapsedIssueIds: observable,
      selectedRow: observable.ref,
      descriptionAwaitingCaret: observable,
      // a row is held over the same place for many pointer moves, each of which sets the same mark again
      dropMark: observable.struct,
      // actions
      toggleIssueCollapse: action,
      setSelectedRow: action,
      awaitDescriptionCaret: action,
      takeTypedForDescription: action,
      setDropMark: action,
    });
  }

  getIsRowSelected = computedFn(
    (issueId: string, groupId: string) => this.selectedRow?.issueId === issueId && this.selectedRow.groupId === groupId
  );

  getIsRowTitleEdited = computedFn(
    (issueId: string, groupId: string) => this.getIsRowSelected(issueId, groupId) && !!this.selectedRow?.isEditing
  );

  getRowDropPlace = computedFn((issueId: string, groupId: string) =>
    this.dropMark?.issueId === issueId && this.dropMark.groupId === groupId ? this.dropMark.place : undefined
  );

  getGroupDropPlace = computedFn((groupId: string) =>
    !this.dropMark?.issueId && this.dropMark?.groupId === groupId ? this.dropMark.place : undefined
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

  setDropMark = (mark: TListDropMark | undefined) => {
    this.dropMark = mark;
  };
}
