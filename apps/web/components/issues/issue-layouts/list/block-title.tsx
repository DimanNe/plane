/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { KeyboardEvent, MouseEvent } from "react";
import { useEffect, useRef } from "react";
import { observer } from "mobx-react";
// plane imports
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TIssue } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { useListView } from "@/hooks/store/use-list-view";

type Props = {
  issue: TIssue;
  groupId: string;
  nestingLevel: number;
  isEditingAllowed: boolean;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
};

// The text size of the title by nesting level; deeper levels take the last. Each is also the name of the theme
// variable that holds the size, by which the list row scales what stands beside the title.
export const TITLE_TEXT_SIZES = ["text-body-sm-medium", "text-body-xs-medium", "text-caption-md-medium"];

/**
 * The title of a list row. A click turns it into an input in place; the name is saved when the focus leaves the input.
 */
export const IssueBlockTitle = observer(function IssueBlockTitle(props: Props) {
  const { issue, groupId, nestingLevel, isEditingAllowed, updateIssue } = props;
  // refs
  const inputRef = useRef<HTMLInputElement | null>(null);
  const caretOffsetRef = useRef(0);
  // hooks
  const { t } = useTranslation();
  const { getIsRowTitleEdited, setSelectedRow } = useListView();
  // derived values
  const isEdited = getIsRowTitleEdited(issue.id, groupId);
  const className = cn("truncate text-primary", TITLE_TEXT_SIZES[Math.min(nestingLevel, 2)]);

  useEffect(() => {
    if (!isEdited) return;
    inputRef.current?.focus();
    inputRef.current?.setSelectionRange(caretOffsetRef.current, caretOffsetRef.current);
  }, [isEdited]);

  const handleClick = (e: MouseEvent) => {
    // with Ctrl or Cmd the click opens the work item in a new tab
    if (!isEditingAllowed || e.metaKey || e.ctrlKey) return;
    // the caret goes where the click landed: the input shows the same text at the same place
    caretOffsetRef.current = document.caretPositionFromPoint?.(e.clientX, e.clientY)?.offset ?? issue.name.length;
    setSelectedRow({ issueId: issue.id, groupId, isEditing: true });
  };

  const handleBlur = (name: string) => {
    if (name.trim() && name.trim() !== issue.name)
      updateIssue?.(issue.project_id, issue.id, { name: name.trim() }).catch(() =>
        setToast({
          type: "error",
          title: t("toast.error"),
          message: t("entity.update.failed", { entity: t("issue.label", { count: 1 }) }),
        })
      );
    // unless the arrow keys have moved the selection to another row by now
    if (getIsRowTitleEdited(issue.id, groupId)) setSelectedRow({ issueId: issue.id, groupId });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "Enter" && e.key !== "Escape") return;
    e.preventDefault();
    // The key ends the editing and nothing else: Escape would also close the work item view beside the list,
    // which listens on the document, as React does.
    e.nativeEvent.stopImmediatePropagation();
    if (e.key === "Escape") e.currentTarget.value = issue.name;
    handleBlur(e.currentTarget.value);
  };

  if (isEdited)
    return (
      <input
        ref={inputRef}
        defaultValue={issue.name}
        maxLength={255}
        aria-label={t("issue.title.label")}
        className={cn(className, "min-w-0 flex-1 bg-transparent outline-none")}
        onBlur={(e) => handleBlur(e.currentTarget.value)}
        onKeyDown={handleKeyDown}
      />
    );

  return (
    // oxlint-disable-next-line jsx_a11y/click-events-have-key-events, jsx_a11y/no-noninteractive-element-interactions
    <p className={cn(className, isEditingAllowed ? "cursor-text" : "cursor-pointer")} onClick={handleClick}>
      {issue.name}
    </p>
  );
});
