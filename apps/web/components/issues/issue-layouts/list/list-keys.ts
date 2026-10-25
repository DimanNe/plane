/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { isTypingInInput } from "@/components/power-k/core/shortcut-handler";

/** Whether the list has the focus where the key was pressed: on the page itself, or on an element of the list. */
export const isPressedInList = (e: KeyboardEvent, list: HTMLElement | null) =>
  e.target === document.body || (e.target instanceof Node && !!list?.contains(e.target));

/**
 * The List layout hears its keys on the document, wherever they are pressed: the arrow keys move its selection, which
 * the work item view beside the list follows, and fold its lines; Enter, E and Delete open, edit and delete the work
 * item of the selected line. The same keys edit text elsewhere on the page, above all in the title and the
 * description of the work item in that view. So a key is the list's only where the list has the focus, and not in a
 * field, an editor, a menu or a dialog there. Every key of the list is asked here, so that a key pressed in the view
 * beside the list, or in any field, never moves the selection or opens another work item.
 */
export const isListKey = (e: KeyboardEvent, list: HTMLElement | null) => {
  // FOR_REVIEWER: decided this way: Delete had this rule already, and now every key of the list has it. Before, an
  // arrow key, Enter or E pressed on a button outside the list (in the view beside the list, in the header, in the
  // sidebar) also moved or opened the list's lines; now such a key is the button's alone. After a dialog closes the
  // focus is on the page (PLANE-72), where the keys stay the list's.
  return !e.defaultPrevented && isPressedInList(e, list) && !isTypingInInput(e.target);
};
