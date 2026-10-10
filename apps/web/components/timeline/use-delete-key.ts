/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
// plane imports
import { useLatestCallback } from "@plane/hooks";

/**
 * The Delete key on what is selected in an element. Only Delete, alone: Backspace is pressed too easily for
 * something that asks nothing before it acts. Not while the focus is where text is typed, where Delete removes a
 * character, nor while it is in another part of the page, which may have its own use for the key. Without
 * `onDelete` the key does nothing here.
 */
export const useDeleteKey = (element: HTMLElement | null, onDelete: (() => void) | undefined) => {
  const handleDelete = useLatestCallback(() => onDelete?.());
  const isListening = !!onDelete;

  useEffect(() => {
    if (!element || !isListening) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      const { key, target } = event;
      if (key !== "Delete" || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
      if (!(target instanceof HTMLElement) || target.isContentEditable || target.matches("input, textarea, select"))
        return;
      // with the focus nowhere the key is pressed on the page itself
      if (target !== document.body && !element.contains(target)) return;
      handleDelete();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [element, isListening, handleDelete]);
};
