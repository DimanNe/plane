/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TIssue } from "@plane/types";

/**
 * A work item that the user has just made is hard to find in a long list: nothing tells its line from the
 * others. Here the line is pointed out: the list brings it into view where the create dialog covered the list,
 * and the line is tinted for a moment where it lands. The look is in styles/new-work-item.css.
 *
 * The dialog does not turn into the line by a view transition of the browser. In a Chrome that was started with
 * --disable-frame-rate-limit such a transition never ends: its picture of the dialog stays over the page, and
 * the page is not drawn again.
 */

const HIGHLIGHT_CLASS_NAME = "new-work-item-highlight";
/** A line is drawn a few frames after its work item is stored, or after the list has scrolled to its place. */
const FRAMES_TO_WAIT_FOR_LINE = 10;

/**
 * The place of a work item in the List layout. The list keeps one for every work item it shows and draws the line
 * in it only near the visible part; the board gives the same id to its cards, which are links.
 * There is none when a filter leaves the work item out, or its group or its parent is folded.
 */
const findListBlock = (workItemId: string) => document.querySelector<HTMLElement>(`div[id^="issue_${workItemId}_"]`);

const findListLine = (workItemId: string) =>
  document.querySelector<HTMLElement>(`[id="issue-${workItemId}"] .group\\/list-block`);

const waitForListLine = async (
  workItemId: string,
  framesLeft = FRAMES_TO_WAIT_FOR_LINE
): Promise<HTMLElement | null> => {
  const line = findListLine(workItemId);
  if (line || framesLeft === 0) return line;
  await new Promise(requestAnimationFrame);
  return waitForListLine(workItemId, framesLeft - 1);
};

const highlightListLine = (line: HTMLElement) => {
  line.classList.add(HIGHLIGHT_CLASS_NAME);
  line.addEventListener("animationend", () => line.classList.remove(HIGHLIGHT_CLASS_NAME), { once: true });
};

/**
 * The list moves only when it does not show the whole place, and then brings it to the middle: at an edge the line
 * would stand behind the message that the work item was created.
 */
const scrollListBlockIntoView = (block: HTMLElement) => {
  const list = block.closest(".vertical-scrollbar") ?? document.body;
  const { left, top, bottom, width } = block.getBoundingClientRect();
  // a group keeps its header at the top of the list, over the lines that are scrolled under it
  const isShownAt = (y: number) =>
    block.contains(document.elementsFromPoint(left + width / 2, y).find((element) => list.contains(element)) ?? null);
  if (!isShownAt(top + 1) || !isShownAt(bottom - 1)) block.scrollIntoView({ block: "center" });
};

/**
 * Tints the line of a work item that was made without a dialog closing over it: from the inline input of a list
 * group, or from the dialog with "Create more" on.
 */
export const highlightNewWorkItem = async (workItemId: string) => {
  const line = await waitForListLine(workItemId);
  if (line) highlightListLine(line);
};

/**
 * Closes the create dialog after it has stored a work item. Where the List layout behind the dialog shows the new
 * work item, the list scrolls to its line, and the line stays tinted for a moment.
 */
export const closeDialogAndPointOutNewWorkItem = (workItem: TIssue, close: () => void) => {
  const block = findListBlock(workItem.id);
  // a sub-work item lands under its parent, where the user is looking already
  if (block && !workItem.parent_id) scrollListBlockIntoView(block);
  close();
  if (block) void highlightNewWorkItem(workItem.id);
};
