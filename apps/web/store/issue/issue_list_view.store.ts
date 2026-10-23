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
  // isEditing: its title is an input; isByHover: the pointer moved over it, which no key or click has confirmed
  selectedRow: { issueId: string; groupId: string; isEditing?: boolean; isByHover?: boolean } | undefined;
  // The selected row before the pointer began to move the selection, for what follows where the user went with a
  // key or a click and not where the pointer passes, such as the address of the page.
  rowBeforeHover: IIssueListViewStore["selectedRow"];
  // The work item whose description is to take the caret (the key E on its line). The view beside the list loads
  // the work item before it has an editor, and what is typed in between is the description's: it is kept here
  // and kept from the shortcuts of the page.
  descriptionAwaitingCaret: string | undefined;
  dropMark: TListDropMark | undefined;
  // The group whose "+" opened the dialog for a new work item: the work item takes what that group stands for,
  // which an empty group or a group other than the one of the selected line can give only this way.
  groupIdOfNewWorkItem: string | undefined;
  // computed
  getIsRowSelected: (issueId: string, groupId: string) => boolean;
  getIsRowTitleEdited: (issueId: string, groupId: string) => boolean;
  getIsRowSelectedByHover: (issueId: string, groupId: string) => boolean;
  getRowDropPlace: (issueId: string, groupId: string) => TListDropMark["place"] | undefined;
  getGroupDropPlace: (groupId: string) => TListDropMark["place"] | undefined;
  // actions
  toggleIssueCollapse: (issueId: string) => void;
  setSelectedRow: (row: IIssueListViewStore["selectedRow"]) => void;
  awaitDescriptionCaret: (issueId: string) => void;
  /** Ends the wait and returns what was typed during it. */
  takeTypedForDescription: () => string;
  /**
   * The state keys have changed the selected line of this work item, and the change is being stored. If it sends
   * the line to another group, the selection is left at the place of the line, for the line that takes it.
   */
  leaveSelectionAtPlaceOf: (issueId: string, change: Promise<unknown>) => void;
  isSelectionLeftAtPlaceOf: (issueId: string) => boolean;
  setDropMark: (mark: TListDropMark | undefined) => void;
  setGroupIdOfNewWorkItem: (groupId: string | undefined) => void;
}

export class IssueListViewStore implements IIssueListViewStore {
  collapsedIssueIds: string[] = [];
  selectedRow: IIssueListViewStore["selectedRow"] = undefined;
  rowBeforeHover: IIssueListViewStore["selectedRow"] = undefined;
  descriptionAwaitingCaret: string | undefined = undefined;
  private typedForDescription = "";
  private issueIdOfPlaceToKeep: string | undefined = undefined;
  dropMark: TListDropMark | undefined = undefined;
  groupIdOfNewWorkItem: string | undefined = undefined;

  constructor() {
    makeObservable(this, {
      collapsedIssueIds: observable,
      selectedRow: observable.ref,
      rowBeforeHover: observable.ref,
      descriptionAwaitingCaret: observable,
      // a row is held over the same place for many pointer moves, each of which sets the same mark again
      dropMark: observable.struct,
      groupIdOfNewWorkItem: observable,
      // actions
      toggleIssueCollapse: action,
      setSelectedRow: action,
      awaitDescriptionCaret: action,
      takeTypedForDescription: action,
      setDropMark: action,
      setGroupIdOfNewWorkItem: action,
    });
  }

  getIsRowSelected = computedFn(
    (issueId: string, groupId: string) => this.selectedRow?.issueId === issueId && this.selectedRow.groupId === groupId
  );

  getIsRowTitleEdited = computedFn(
    (issueId: string, groupId: string) => this.getIsRowSelected(issueId, groupId) && !!this.selectedRow?.isEditing
  );

  getIsRowSelectedByHover = computedFn(
    (issueId: string, groupId: string) => this.getIsRowSelected(issueId, groupId) && !!this.selectedRow?.isByHover
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
    if (!row?.isByHover) this.rowBeforeHover = undefined;
    else if (!this.selectedRow?.isByHover) this.rowBeforeHover = this.selectedRow;
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

  // Only while the change is being stored: a line that this change does not move, and that goes to another group
  // later for another reason, takes the selection with it as every line does.
  leaveSelectionAtPlaceOf = (issueId: string, change: Promise<unknown>) => {
    const forget = () => {
      if (this.issueIdOfPlaceToKeep === issueId) this.issueIdOfPlaceToKeep = undefined;
    };
    this.issueIdOfPlaceToKeep = issueId;
    void change.then(forget, forget);
  };

  isSelectionLeftAtPlaceOf = (issueId: string) => this.issueIdOfPlaceToKeep === issueId;

  setDropMark = (mark: TListDropMark | undefined) => {
    this.dropMark = mark;
  };

  setGroupIdOfNewWorkItem = (groupId: string | undefined) => {
    this.groupIdOfNewWorkItem = groupId;
  };
}
