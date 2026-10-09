/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext } from "react";
// mobx store
import { StoreContext } from "@/lib/store-context";
// types
import type { IIssueListViewStore } from "@/store/issue/issue_list_view.store";

export const useListView = (): IIssueListViewStore => {
  const context = useContext(StoreContext);
  if (context === undefined) throw new Error("useListView must be used within StoreProvider");
  return context.issue.issueListView;
};
