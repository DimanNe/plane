/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RefObject } from "react";
import { useCallback, useEffect, useState } from "react";
// plane imports
import type { EditorRefApi } from "@plane/editor";
// hooks
import { useListView } from "@/hooks/store/use-list-view";

/**
 * Gives the caret to the description of a work item in the view beside the list, at its very beginning, when the
 * key E on its line asked for it (hooks/use-list-row-edit.ts). The view makes the editor of the description some
 * time after it opened, and makes a new one for another work item, so the caret is given when an editor is there.
 * A user who may not edit gets no caret.
 *
 * Returns what the editor of the description calls when it is made.
 */
export const useDescriptionCaret = (
  issueId: string,
  editorRef: RefObject<EditorRefApi | null>,
  isEditable: boolean
) => {
  // store hooks
  const { descriptionAwaitingCaret, takeTypedForDescription } = useListView();
  // states
  const [issueIdOfEditor, setIssueIdOfEditor] = useState<{ issueId: string }>();
  // derived values
  const isCaretAwaited = descriptionAwaitingCaret === issueId && issueIdOfEditor?.issueId === issueId;

  useEffect(() => {
    if (!isCaretAwaited) return;
    if (!isEditable) {
      takeTypedForDescription();
      return;
    }
    // The editor takes the focus a frame after it is asked to. What is typed until then is still kept, and goes
    // into the description with the rest.
    const typeKeptText = () => {
      const typedText = takeTypedForDescription();
      if (typedText) editorRef.current?.setEditorValueAtCursorPosition(typedText);
    };
    document.addEventListener("focusin", typeKeptText, { once: true });
    editorRef.current?.focus("start");
    return () => document.removeEventListener("focusin", typeKeptText);
  }, [isCaretAwaited, issueIdOfEditor, isEditable, editorRef, takeTypedForDescription]);

  // a new object for every editor that is made: one made later for the same work item is asked again
  return useCallback(
    (isReady: boolean) => {
      if (isReady) setIssueIdOfEditor({ issueId });
    },
    [issueId]
  );
};
