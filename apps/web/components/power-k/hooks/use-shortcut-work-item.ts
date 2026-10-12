/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";
// local imports
import type { TPowerKContext } from "../core/types";

/**
 * The work item that a shortcut acts on: the one of the peek view or of the work item page, else the selected line
 * of the list. The stores are read when a key is pressed, so moving the selection does not build the commands
 * again.
 */
export const useShortcutWorkItemId = () => {
  const issueDetail = useIssueDetail();
  const listView = useListView();

  return (ctx: TPowerKContext) =>
    issueDetail.peekIssue?.issueId ??
    (ctx.params.workItem
      ? issueDetail.issue.getIssueIdByIdentifier(ctx.params.workItem.toString())
      : listView.selectedRow?.issueId);
};
