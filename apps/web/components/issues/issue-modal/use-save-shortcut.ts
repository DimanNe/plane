/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RefObject } from "react";
import { useEffect, useRef } from "react";
// plane imports
import type { EditorRefApi } from "@plane/editor";
import { useLatestCallback } from "@plane/hooks";

type TArgs = {
  formRef: RefObject<HTMLFormElement | null>;
  editorRef: RefObject<EditorRefApi | null>;
  // the dialog's primary button: the keys do nothing when it is absent or disabled
  submitButtonRef: RefObject<HTMLButtonElement | null>;
  // what a press on that button runs
  submit: () => Promise<unknown>;
};

/**
 * Ctrl+S and Ctrl+Enter do what the primary button of the work item dialog does, wherever the focus is in the
 * dialog. While a menu of the dialog is open, and in a dialog that opened above it, the keys are left alone.
 */
export const useSaveShortcut = ({ formRef, editorRef, submitButtonRef, submit }: TArgs) => {
  const submitting = useRef<Promise<unknown>>(undefined);
  const submitLatest = useLatestCallback(submit);

  const handleKeyDown = useLatestCallback((event: KeyboardEvent) => {
    if (!event.ctrlKey || event.altKey || event.shiftKey || event.metaKey) return;
    if (event.key !== "Enter" && event.key.toLowerCase() !== "s") return;
    const dialog = formRef.current?.closest('[role="dialog"]');
    // a menu and a dialog above this one are outside it in the page, and take the focus
    if (!dialog || !(event.target instanceof Node) || !dialog.contains(event.target)) return;
    if (dialog.querySelector('[aria-expanded="true"]') || editorRef.current?.isAnyDropbarOpen()) return;
    // The browser would offer to save the page, the editor would break the line, and the page behind the dialog
    // may have its own meaning for these keys.
    event.preventDefault();
    event.stopPropagation();
    const button = submitButtonRef.current;
    if (event.repeat || submitting.current || !button || button.disabled) return;
    // A press on the button takes the focus from the field that has it, and a field that keeps what is typed
    // until it is left gives it to the form then. The same here, with the focus back where it was.
    const focused = document.activeElement;
    if (focused instanceof HTMLElement) {
      focused.blur();
      focused.focus({ preventScroll: true });
    }
    submitting.current = submitLatest().finally(() => {
      submitting.current = undefined;
    });
  });

  // on the document and before everybody else: the editor handles Ctrl+Enter itself when the key reaches it
  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [handleKeyDown]);
};
