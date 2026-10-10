/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { flushSync } from "react-dom";
import type { TIssue } from "@plane/types";

/**
 * A work item that the user has just made is hard to find in a long list: nothing tells its line from the
 * others. Here the line is pointed out. Saved from the create dialog, the dialog turns into the line; in the
 * other cases the line is tinted for a moment where it lands. The looks are in styles/new-work-item.css.
 */

/** Shared by the dialog and the line for the time of one view transition, which makes one turn into the other. */
const VIEW_TRANSITION_NAME = "new-work-item";
/**
 * On the page for the time of that view transition. An attribute and not a class: the styles of the editor ask
 * about the classes of every element's ancestors, so a class that changes on the page restyles the whole page.
 */
const ARRIVING_ATTRIBUTE = "data-new-work-item-arriving";
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
 * A copy of the dialog for the view transition to start from, laid out where the dialog is. The dialog itself
 * closes as it does without a transition: the browser starts a transition some frames after it is asked to, and
 * a dialog that stayed open until then would take the keys that the user types next.
 */
const makePictureOfDialog = (dialog: HTMLElement) => {
  const box = dialog.cloneNode(true) as HTMLElement;
  box.style.viewTransitionName = VIEW_TRANSITION_NAME;
  // the classes of the dialog's parent put the dialog's box in its place over the page, and the copy likewise
  const picture = document.createElement("div");
  picture.className = dialog.parentElement?.className ?? "";
  picture.inert = true;
  picture.append(box);
  return picture;
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
 * work item, the list scrolls to its line, the dialog turns into the line, and the line stays tinted for a moment.
 * Resolves when the dialog is closed, so that the caller empties the form unseen.
 */
export const closeDialogIntoNewWorkItem = async (workItem: TIssue, dialog: HTMLElement | null, close: () => void) => {
  const block = findListBlock(workItem.id);
  if (!block) return close();
  // a sub-work item lands under its parent, where the user is looking already
  if (workItem.parent_id) {
    close();
    void highlightNewWorkItem(workItem.id);
    return;
  }

  scrollListBlockIntoView(block);
  const line = await waitForListLine(workItem.id);
  const canMorph =
    dialog !== null &&
    line !== null &&
    typeof document.startViewTransition === "function" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!canMorph) {
    close();
    if (line) highlightListLine(line);
    return;
  }

  const picture = makePictureOfDialog(dialog);
  // The line is in the list already, behind the dialog. Its place stays empty until the dialog's box arrives there.
  line.style.visibility = "hidden";
  document.documentElement.toggleAttribute(ARRIVING_ATTRIBUTE, true);
  // The dialog leaves the page before the picture enters it, so that each is the last child of the body when it
  // goes or comes: for a change among the body's children anywhere else the browser restyles the whole page.
  flushSync(close);
  document.body.append(picture);
  const transition = document.startViewTransition(() => {
    picture.remove();
    line.style.visibility = "";
    line.style.viewTransitionName = VIEW_TRANSITION_NAME;
    highlightListLine(line);
  });
  void transition.finished.finally(() => {
    line.style.viewTransitionName = "";
    document.documentElement.toggleAttribute(ARRIVING_ATTRIBUTE, false);
  });
};
