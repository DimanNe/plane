/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef } from "react";
import { useParams } from "next/navigation";
// plane imports
import { hasContextMenuItem, runContextMenuItem } from "@plane/blocks/context-menu";
import { setToast } from "@plane/blocks/toast";
import { EUserPermissions, EUserPermissionsLevel, PROJECT_ERROR_MESSAGES } from "@plane/constants";
import { useLatestCallback } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";
import type { TIssue, TIssueMap } from "@plane/types";
// components
import { isListKey } from "@/components/issues/issue-layouts/list/list-keys";
import type { TListRow } from "@/components/issues/issue-layouts/list/utils";
import { getIssueBlockId } from "@/components/issues/issue-layouts/utils";
// hooks
import { useUser, useUserPermissions } from "@/hooks/store/user";
import { useIssueStoreType } from "@/hooks/use-issue-layout-store";
import { useIssuesActions } from "@/hooks/use-issues-actions";
import useKeypress from "@/hooks/use-keypress";

/** The key of the item "Delete" in the right-click menu of a list row (quick-action-dropdowns/helper.tsx). */
const DELETE_MENU_ITEM_KEY = "delete";

type TRow = TListRow & { groupId: string };

type Props = {
  containerRef: React.MutableRefObject<HTMLElement | null>;
  rows: TRow[];
  selectedRowIndex: number;
  issuesMap: TIssueMap;
};

/**
 * The Delete key on the selected row of the List layout. It does what "Delete" of the row's right-click menu
 * does, and only where that menu has it for this user and this work item: the menu itself is asked. Alone
 * the key opens the menu's question; with Shift the work item is deleted without one.
 *
 * Only Delete: Backspace is pressed too easily for a key that removes a work item. Only where the key is the list's
 * (see list-keys.ts), not in the work item view beside the list nor in a field. A held key deletes once.
 *
 * Returns the row that takes the place of a row deleted this way, for the selection to go on from.
 */
export const useListRowDelete = (props: Props) => {
  const { containerRef, rows, selectedRowIndex, issuesMap } = props;
  // router
  const { workspaceSlug } = useParams();
  // hooks
  const { t } = useTranslation();
  const { data: currentUser } = useUser();
  const { allowPermissions } = useUserPermissions();
  const { removeIssue } = useIssuesActions(useIssueStoreType());
  // refs
  const keyedIssueIdRef = useRef<string | undefined>(undefined);
  const lastSelectedRowIndexRef = useRef(-1);

  useEffect(() => {
    if (selectedRowIndex !== -1) lastSelectedRowIndexRef.current = selectedRowIndex;
  }, [selectedRowIndex]);

  // The menu's question, once answered, refuses a user who neither made the work item nor is an admin of its
  // project, and tells how it went (components/issues/delete-issue-modal.tsx). The same here, without the question.
  const deleteWithoutQuestion = async (issue: TIssue) => {
    const isAuthorized =
      issue.created_by === currentUser?.id ||
      allowPermissions(
        [EUserPermissions.ADMIN],
        EUserPermissionsLevel.PROJECT,
        workspaceSlug?.toString(),
        issue.project_id ?? undefined
      );
    if (!isAuthorized) {
      setToast({ type: "error", title: t(PROJECT_ERROR_MESSAGES.permissionError.i18n_title) });
      return;
    }
    try {
      await removeIssue(issue.project_id, issue.id);
      setToast({
        type: "success",
        title: t("common.success"),
        message: t("entity.delete.success", { entity: t("common.work_item") }),
      });
    } catch {
      const { i18n_title, i18n_message } = PROJECT_ERROR_MESSAGES.issueDeleteError;
      setToast({ type: "error", title: t(i18n_title), message: t(i18n_message) });
    }
  };

  useKeypress("Delete", (e) => {
    const row = rows[selectedRowIndex];
    const issue = row && issuesMap[row.issueId];
    // a row that the list has not drawn, far from the visible part, is not deleted unseen
    const rowElement =
      row &&
      document.getElementById(getIssueBlockId(row.issueId, row.groupId))?.querySelector('[class~="group/list-block"]');
    if (e.ctrlKey || e.metaKey || e.altKey || e.repeat || !isListKey(e, containerRef.current)) return;
    if (!issue || !rowElement) return;
    const isOffered = e.shiftKey
      ? hasContextMenuItem(rowElement, DELETE_MENU_ITEM_KEY)
      : runContextMenuItem(rowElement, DELETE_MENU_ITEM_KEY);
    if (!isOffered) return;
    e.preventDefault();
    keyedIssueIdRef.current = issue.id;
    if (e.shiftKey) void deleteWithoutQuestion(issue);
  });

  /**
   * The row that stands where the selected row last stood, now that its work item has gone from there: deleted,
   * or in another group. Where the list ends before that place, the last row.
   */
  const getRowAtSelectedPlace = useLatestCallback((goneIssueId: string) => {
    const otherRows = rows.filter((row) => row.issueId !== goneIssueId);
    return otherRows[Math.min(lastSelectedRowIndexRef.current, otherRows.length - 1)];
  });

  /**
   * The row where the work item stood that the key deleted, or the last row. Nothing for a work item that left
   * the list another way, or that is still there: the question may have been answered with Cancel, and the work
   * item may leave the list later for another reason, such as a filter.
   */
  const getRowInPlaceOf = useLatestCallback((issueId: string) => {
    if (keyedIssueIdRef.current !== issueId || issuesMap[issueId]) return undefined;
    return getRowAtSelectedPlace(issueId);
  });

  return { getRowInPlaceOf, getRowAtSelectedPlace };
};
