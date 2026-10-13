/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { flushSync } from "react-dom";
import type { TIssue } from "@plane/types";

/**
 * A work item that the user has just made is hard to find in a long list: nothing tells its line from the
 * others. Here the line is pointed out: the list brings it into view where the create dialog covered the list,
 * the dialog turns into the line, and the line is tinted for a moment where it lands.
 *
 * The dialog does not turn into the line by a view transition of the browser. In a Chrome that was started with
 * --disable-frame-rate-limit such a transition never ends: its picture of the dialog stays over the page, and
 * the page is not drawn again. A box of this file's own goes from the dialog's place to the line's instead.
 */

const TINT = "var(--background-color-accent-subtle)";
/** Long enough to outlast the dialog's way to the line, and to find the line where the dialog only closes. */
const TINT_DURATION = 2400;
const MORPH_CLASS_NAME = "new-work-item-morph";
const MORPH_DURATION = 320;
/** The box's way is given to the browser as this many straight pieces. */
const MORPH_STEPS = 16;
/** The part of its time after which the box goes out, unless the page has seen the line by then. */
const MORPH_DISSOLVE_START = 0.75;
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

/**
 * The line stays tinted for a moment, then the tint fades into the line's own background. The tint is an
 * animation of the line and not a class: the list writes the line's classes anew when the line is selected.
 */
const highlightListLine = (line: HTMLElement) =>
  line.animate([{ backgroundColor: TINT }, { backgroundColor: TINT, offset: 0.4, easing: "ease-out" }], TINT_DURATION);

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

const addLayer = (parent: HTMLElement, name: string, content?: Node) => {
  const layer = document.createElement("div");
  layer.className = `${MORPH_CLASS_NAME}-${name}`;
  if (content) layer.append(content);
  return parent.appendChild(layer);
};

/**
 * The box at each step of its way from one rectangle to the other, fast at first and slow into its place. The
 * box is laid out where it ends and only moved and scaled from there, and what it shows is scaled the other way,
 * so that nothing in it is stretched. The browser can then run the whole way without the page: a page that is
 * busy with the list after a save would hold up a box whose size it had to lay out for every frame.
 */
const getMorphKeyframes = (from: DOMRect, to: DOMRect) => {
  const steps = Array.from({ length: MORPH_STEPS + 1 }, (_, step) => {
    const wayToGo = (1 - step / MORPH_STEPS) ** 3;
    const scaleX = (to.width + (from.width - to.width) * wayToGo) / to.width;
    const scaleY = (to.height + (from.height - to.height) * wayToGo) / to.height;
    return { x: (from.left - to.left) * wayToGo, y: (from.top - to.top) * wayToGo, scaleX, scaleY };
  });
  return {
    box: steps.map(({ x, y, scaleX, scaleY }) => ({
      transform: `translate(${x}px, ${y}px) scale(${scaleX}, ${scaleY})`,
    })),
    content: steps.map(({ scaleX, scaleY }) => ({ transform: `scale(${1 / scaleX}, ${1 / scaleY})` })),
  };
};

/**
 * Closes the dialog and sends a box from its place to the line of the work item: the box starts as the dialog's
 * picture, takes the colour of the tint, and ends as the tinted line's picture exactly over the line, which is
 * not shown until then. The box is not part of the page: it takes no click and no key, and it goes by
 * itself when its time is over, whatever has become of the list meanwhile.
 *
 * A box at rest must lie on the line. Where the list had to scroll far, the page draws the line only later, and
 * may be too busy with the list to do it in the box's time; the browser, which moves the box without the page,
 * would then leave it at rest where nobody has seen the line. So the box is set to go out as it arrives, and
 * stays whole only once the page has seen the line drawn.
 */
const morphDialogIntoLine = (workItemId: string, dialog: HTMLElement, block: HTMLElement, close: () => void) => {
  const from = dialog.getBoundingClientRect();
  const box = document.createElement("div");
  box.className = MORPH_CLASS_NAME;
  box.inert = true;
  const surface = addLayer(box, "surface");
  surface.style.backgroundColor = TINT;
  const content = addLayer(box, "content");
  const dialogLayer = addLayer(content, "dialog", dialog.cloneNode(true));
  const lineLayer = addLayer(content, "line");
  Object.assign(dialogLayer.style, { width: `${from.width}px`, height: `${from.height}px` });

  // The dialog leaves the page before the box enters it, so that each is the last child of the body when it goes
  // or comes: for a change among the body's children anywhere else the browser restyles the whole page.
  flushSync(close);
  document.body.append(box);

  const timing = { duration: MORPH_DURATION };
  const boxAnimation = box.animate(null, timing);
  const contentAnimation = content.animate(null, timing);
  // one picture leaves while the other comes, over the colour of the tint
  surface.animate({ opacity: [0, 1, 1], offset: [0, 0.2, 1] }, timing);
  dialogLayer.animate({ opacity: [1, 1, 0, 0], offset: [0, 0.1, 0.45, 1] }, timing);
  lineLayer.animate({ opacity: [0, 0, 1, 1], offset: [0, 0.35, 0.7, 1] }, timing);
  block.animate({ opacity: [0, 0] }, timing);
  const dissolve = box.animate(
    { opacity: [1, 1, 0], offset: [0, MORPH_DISSOLVE_START, 1] },
    { ...timing, fill: "forwards" }
  );
  void boxAnimation.finished.then(() => {
    box.remove();
    // a line that was not drawn in the box's time gets its tint when it is
    return lineLayer.hasChildNodes() ? undefined : highlightNewWorkItem(workItemId);
  });

  // The box sets off for the line's place at once and follows it from there. In a narrow window a line with many
  // values is higher than what stands in for it, so lines that the list draws meanwhile can still move this one,
  // also out of view again.
  let to: DOMRect | undefined;
  const followLine = () => {
    const line = findListLine(workItemId);
    const target = line ?? block;
    if (!box.isConnected || !target.isConnected) return;
    scrollListBlockIntoView(block);
    if (line && !lineLayer.hasChildNodes()) {
      highlightListLine(line);
      const lineCopy = line.cloneNode(true) as HTMLElement;
      lineCopy.style.backgroundColor = TINT;
      lineLayer.append(lineCopy);
      // a box that has begun to go out goes on: coming back would flicker
      if (Number(boxAnimation.currentTime) < MORPH_DURATION * MORPH_DISSOLVE_START) dissolve.cancel();
    }
    const rect = target.getBoundingClientRect();
    if (rect.left !== to?.left || rect.top !== to.top || rect.width !== to.width || rect.height !== to.height) {
      to = rect;
      const { left, top, width, height } = to;
      const keyframes = getMorphKeyframes(from, to);
      Object.assign(box.style, { left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px` });
      lineLayer.style.width = `${width}px`;
      (boxAnimation.effect as KeyframeEffect).setKeyframes(keyframes.box);
      (contentAnimation.effect as KeyframeEffect).setKeyframes(keyframes.content);
    }
    requestAnimationFrame(followLine);
  };
  followLine();
};

/** Whether the List layout on the page shows a line of the work item. */
export const hasListLine = (workItemId: string) => findListBlock(workItemId) !== null;

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
 */
export const closeDialogAndPointOutNewWorkItem = async (
  workItem: TIssue,
  dialog: HTMLElement | null,
  close: () => void
) => {
  const block = findListBlock(workItem.id);
  // a sub-work item lands under its parent, where the user is looking already
  const isLineElsewhere = block !== null && !workItem.parent_id;
  if (isLineElsewhere && dialog && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    morphDialogIntoLine(workItem.id, dialog, block, close);
    return;
  }
  if (isLineElsewhere) scrollListBlockIntoView(block);
  close();
  if (!block) return;
  await highlightNewWorkItem(workItem.id);
  // the lines around it are drawn by now too; in a narrow window they may have pushed it out of view again
  if (isLineElsewhere) scrollListBlockIntoView(block);
};
