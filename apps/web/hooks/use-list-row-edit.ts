/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
// plane imports
import { useLatestCallback } from "@plane/hooks";
// components
import { isListKey } from "@/components/issues/issue-layouts/list/list-keys";
import type { TListRow } from "@/components/issues/issue-layouts/list/utils";
import { resolveShortcutKey } from "@/components/power-k/core/shortcut-handler";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";

type Props = {
  containerRef: React.MutableRefObject<HTMLElement | null>;
  selectedRow: TListRow | undefined;
  openRow: (row: TListRow) => void;
};

/**
 * The key E on the selected line of the List layout: its work item opens in the view beside the list, and the
 * caret stands at the start of its description (hooks/use-description-caret.ts gives it the caret). A view that
 * shows the work item already stays as it is.
 *
 * Only where the key is the list's (see list-keys.ts), not where it is typed text or has another meaning.
 */
export const useListRowEdit = (props: Props) => {
  const { containerRef, selectedRow, openRow } = props;
  // store hooks
  const { descriptionAwaitingCaret, awaitDescriptionCaret, takeTypedForDescription } = useListView();
  const { peekIssue } = useIssueDetail();

  const handleKeyDown = useLatestCallback((e: KeyboardEvent) => {
    // the key by its place on the keyboard where the layout has no Latin letters, as the shortcuts of the app
    if (resolveShortcutKey(e, null) !== "e" || !selectedRow) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.repeat) return;
    if (!isListKey(e, containerRef.current)) return;
    e.preventDefault();
    if (peekIssue?.issueId !== selectedRow.issueId) openRow(selectedRow);
    awaitDescriptionCaret(selectedRow.issueId);
  });

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // A view that was closed, or that shows another work item by now, will not give the caret to this description.
  useEffect(() => {
    if (descriptionAwaitingCaret && peekIssue?.issueId !== descriptionAwaitingCaret) takeTypedForDescription();
  }, [descriptionAwaitingCaret, peekIssue, takeTypedForDescription]);

  // nor will a list that is gone
  useEffect(() => () => void takeTypedForDescription(), [takeTypedForDescription]);
};
