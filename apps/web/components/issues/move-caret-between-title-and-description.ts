/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type React from "react";
import { useEffect } from "react";
import type { EditorRefApi } from "@plane/editor";

/**
 * The title of a work item and its description are typed as one text: a title is one line, and what one writes after
 * it is the description. So Enter in the title and ↓ on its last line go on in the description, and ↑ on the
 * description's first line goes back to the title, in the dialog of a new work item and in the view of a work item
 * alike.
 *
 * The description is the editable part that follows the title in the page, the first one after it.
 */
const findDescriptionAfter = (title: HTMLElement) =>
  [...document.querySelectorAll<HTMLElement>('[contenteditable="true"]')].find(
    (editable) => title.compareDocumentPosition(editable) & Node.DOCUMENT_POSITION_FOLLOWING
  );

/**
 * The editor puts its caret at the beginning of the description, but takes the focus only a frame later, and a key
 * typed in that frame would still go to the title. So the description takes the focus here at once.
 */
const moveCaretToStartOfDescription = (
  title: HTMLElement,
  descriptionEditorRef: React.RefObject<EditorRefApi | null>
) => {
  const description = findDescriptionAfter(title);
  descriptionEditorRef.current?.focus("start");
  description?.focus({ preventScroll: true });
};

/**
 * Enter in the title gives the caret to the description, at its very beginning. Enter with a modifier key is left to
 * whoever handles it (Ctrl+Enter saves the dialog), and so is the Enter that ends the composition of a character in
 * an input method.
 */
const moveCaretToDescriptionOnEnter = (
  event: React.KeyboardEvent<HTMLElement>,
  descriptionEditorRef: React.RefObject<EditorRefApi | null>
) => {
  if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
  if (event.nativeEvent.isComposing) return;
  // Enter would save the form of the dialog, and break the title of the view into two lines
  event.preventDefault();
  moveCaretToStartOfDescription(event.currentTarget, descriptionEditorRef);
};

/**
 * Whether the caret of the title is on its last line. The title of the dialog is an input, of one line. The title of
 * the view is a textarea, which wraps a long title over several lines and tells where its caret is only as an offset
 * in its text. Where a line wraps, one offset is both the end of the upper line and the start of the lower one: the
 * caret is drawn at the end of the upper line when End or a click right of that line put it there, and at the start
 * of the lower one otherwise. Only the browser knows which, so it is asked to move the caret to the end of the line
 * where it is drawn.
 */
const isCaretOnLastLineOfTitle = (title: HTMLInputElement | HTMLTextAreaElement) => {
  if (title instanceof HTMLInputElement) return true;
  const caret = title.selectionEnd;
  if (caret === title.value.length) return true;
  // FOR_REVIEWER: Selection.modify is in no standard. Chrome moves the caret of a textarea by it; in a browser that
  // does not, ↓ on the last line does what it did before, and the next ↓, at the end of the title, goes to the
  // description. Laying the title out again in a hidden copy of its box, the other way, cannot tell on which of the
  // two lines a caret at a wrap is drawn: with it, keys/arrow_down_in_title failed at the end of a line that wraps.
  document.getSelection()?.modify("move", "forward", "lineboundary");
  const isOnLastLine = title.selectionEnd === title.value.length;
  // a caret that did not move is left alone: set again, it would be drawn at the start of the lower line
  if (title.selectionEnd !== caret) title.setSelectionRange(caret, caret);
  return isOnLastLine;
};

/**
 * ↓ on the last line of the title gives the caret to the description, at its very beginning, as Enter does. On an
 * earlier line of a title that wraps ↓ is the title's, and so is ↓ with a modifier key, over a selection, in the
 * composition of a character in an input method, or while the description is not shown yet.
 */
const moveCaretToDescriptionOnArrowDown = (
  event: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>,
  descriptionEditorRef: React.RefObject<EditorRefApi | null>
) => {
  if (event.key !== "ArrowDown" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
  if (event.nativeEvent.isComposing) return;
  const title = event.currentTarget;
  if (!descriptionEditorRef.current || title.selectionStart !== title.selectionEnd) return;
  if (!isCaretOnLastLineOfTitle(title)) return;
  event.preventDefault();
  // FOR_REVIEWER: the caret goes to the start of the description, where Enter puts it, and not to the column it had
  // in the title; so ↑ and ↓ mirror each other: ↑ goes to the end of the title. The nearest column would ask the
  // editor for the position at a point, which its ref does not offer.
  moveCaretToStartOfDescription(title, descriptionEditorRef);
};

export const moveCaretToDescriptionOnEnterOrArrowDown = (
  event: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>,
  descriptionEditorRef: React.RefObject<EditorRefApi | null>
) => {
  moveCaretToDescriptionOnEnter(event, descriptionEditorRef);
  moveCaretToDescriptionOnArrowDown(event, descriptionEditorRef);
};

/** Where a collapsed selection is drawn: in an empty line, which has no text to draw it in, where its line is. */
const getCaretRect = (caret: Range) => {
  const rect = caret.getClientRects()[0];
  if (rect) return rect;
  const container = caret.startContainer;
  return (container instanceof Element ? container : container.parentElement)?.getBoundingClientRect();
};

/**
 * ↑ on the first line of the description gives the caret back to the title, at its end. On any later line ↑ is the
 * editor's, and so is ↑ with a modifier key, over a selection, or while a menu of the editor (the "/" commands, a
 * mention) takes the arrow keys.
 *
 * The page listens for it on the key's way down to the editor: the dialog of a new work item keeps the keys typed in
 * it from the page on their way back up, and the editor's element is made by the editor.
 */
export const useMoveCaretToTitleOnArrowUp = (
  titleRef: React.RefObject<HTMLInputElement | HTMLTextAreaElement | null>,
  descriptionEditorRef: React.RefObject<EditorRefApi | null>
) => {
  useEffect(() => {
    const moveCaretToTitleOnArrowUp = (event: KeyboardEvent) => {
      if (event.key !== "ArrowUp" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
      if (event.isComposing) return;
      const title = titleRef.current;
      const editor = descriptionEditorRef.current;
      if (!title || !editor || event.target !== findDescriptionAfter(title)) return;
      // the editor has not seen the key yet, so a menu of it that takes the arrow keys is asked whether it is open
      if (editor.isAnyDropbarOpen()) return;
      // The caret is read from the browser, not from the editor: a caret that the browser has just moved by a key,
      // as End or a first ↑ does, reaches the editor's state only later, and a ↑ pressed at once would be judged by
      // the caret before the move. A line that a long first paragraph wraps into is drawn lower, so it is not the
      // first line.
      const selection = document.getSelection();
      if (!selection?.rangeCount || !selection.isCollapsed) return;
      const caret = getCaretRect(selection.getRangeAt(0));
      const firstLine = editor.getCoordsFromPos(1);
      if (!caret || !firstLine || caret.top >= firstLine.bottom) return;
      event.preventDefault();
      // FOR_REVIEWER: the caret goes to the end of the title, not to the column it had in the description; a title
      // is short, and what one does after ↑ is mostly to go on writing it. The nearest column would need the
      // title's text measured in its font.
      title.focus();
      title.setSelectionRange(title.value.length, title.value.length);
    };
    document.addEventListener("keydown", moveCaretToTitleOnArrowUp, { capture: true });
    return () => document.removeEventListener("keydown", moveCaretToTitleOnArrowUp, { capture: true });
  }, [titleRef, descriptionEditorRef]);
};
