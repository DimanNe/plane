/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type React from "react";

/**
 * Enter in the title of a work item gives the caret to its description, at its very beginning, as the next line of
 * one text would: a title is one line, and what one writes after it is the description. So it is in the dialog of a
 * new work item and in the view of a work item. Enter with a modifier key is left to whoever handles it (Ctrl+Enter
 * saves the dialog), and so is the Enter that ends the composition of a character in an input method.
 *
 * `moveCaretToDescription` puts the editor's caret at the beginning of the description; the editor takes the focus
 * only a frame later, and a key typed in that frame would still go to the title. So the editable part of the
 * description, the first one after the title in the page, takes the focus here at once.
 */
export const moveCaretToDescriptionOnEnter = (
  event: React.KeyboardEvent<HTMLElement>,
  moveCaretToDescription: () => void
) => {
  if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
  if (event.nativeEvent.isComposing) return;
  // Enter would save the form of the dialog, and break the title of the view into two lines
  event.preventDefault();
  const title = event.currentTarget;
  const description = [...document.querySelectorAll<HTMLElement>('[contenteditable="true"]')].find(
    (editable) => title.compareDocumentPosition(editable) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  moveCaretToDescription();
  description?.focus({ preventScroll: true });
};
