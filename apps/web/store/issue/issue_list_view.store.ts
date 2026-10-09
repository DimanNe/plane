/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable } from "mobx";

export interface IIssueListViewStore {
  collapsedIssueIds: string[];
  // actions
  toggleIssueCollapse: (issueId: string) => void;
}

export class IssueListViewStore implements IIssueListViewStore {
  collapsedIssueIds: string[] = [];

  constructor() {
    makeObservable(this, {
      collapsedIssueIds: observable,
      // actions
      toggleIssueCollapse: action,
    });
  }

  toggleIssueCollapse = (issueId: string) => {
    this.collapsedIssueIds = this.collapsedIssueIds.includes(issueId)
      ? this.collapsedIssueIds.filter((id) => id !== issueId)
      : [...this.collapsedIssueIds, issueId];
  };
}
