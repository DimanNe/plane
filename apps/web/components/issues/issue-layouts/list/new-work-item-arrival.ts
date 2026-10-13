/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { flushSync } from "react-dom";
import type { TIssue } from "@plane/types";
import { getIssueBlockId } from "../utils";

/**
 * A work item that the user has just made is hard to find in a long list: nothing tells its line from the
 * others. Here the line is pointed out: the list brings it into view where the create dialog covered the list,
 * the dialog turns into the line, and the line is tinted for a moment where it lands. A line that a change of
 * its work item sends to another group of the list is as hard to follow, and is pointed out the same way: it is
 * seen going from its old place to its new one.
 *
 * Nothing here is a view transition of the browser. In a Chrome that was started with
 * --disable-frame-rate-limit such a transition never ends: its picture of the dialog stays over the page, and
 * the page is not drawn again. A box of this file's own goes to the line's place instead.
 */

/** Strong enough to be found at a glance, also on a selected line, and pale enough to be read as a tint. */
const TINT = "var(--background-color-accent-subtle-active)";
/** Long enough to outlast the box's way to the line, and to find the line where the dialog only closes. */
const TINT_DURATION = 2400;
const MORPH_CLASS_NAME = "new-work-item-morph";
const MORPH_DURATION = 320;
/** The box's way is given to the browser as this many straight pieces. */
const MORPH_STEPS = 16;
/** The part of its time after which the box goes out, unless the page has seen the line by then. */
const MORPH_DISSOLVE_START = 0.75;
/** A line is drawn a few frames after its work item is stored, or after the list has scrolled to its place. */
const FRAMES_TO_WAIT_FOR_LINE = 10;
const LINE_SELECTOR = ".group\\/list-block";

/**
 * The place of a work item in the List layout. The list keeps one for every work item it shows and draws the line
 * in it only near the visible part; the board gives the same id to its cards, which are links.
 * There is none when a filter leaves the work item out, or its group or its parent is folded.
 */
const findListBlock = (workItemId: string) => document.querySelector<HTMLElement>(`div[id^="issue_${workItemId}_"]`);

const findListLine = (workItemId: string) =>
  document.querySelector<HTMLElement>(`[id="issue-${workItemId}"] ${LINE_SELECTOR}`);

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

/** Whether the list shows a place: all of it, or at least its upper or its lower edge. */
const isShownInList = (place: HTMLElement, isAllOfIt: boolean) => {
  const list = place.closest(".vertical-scrollbar") ?? document.body;
  const { left, top, bottom, width } = place.getBoundingClientRect();
  // a group keeps its header at the top of the list, over the lines that are scrolled under it
  const isShownAt = (y: number) =>
    place.contains(document.elementsFromPoint(left + width / 2, y).find((element) => list.contains(element)) ?? null);
  return isAllOfIt ? isShownAt(top + 1) && isShownAt(bottom - 1) : isShownAt(top + 1) || isShownAt(bottom - 1);
};

/**
 * The list moves only when it does not show the whole place, and then brings it to the middle: at an edge the line
 * would stand behind the message that the work item was created.
 */
const scrollListBlockIntoView = (block: HTMLElement) => {
  if (!isShownInList(block, true)) block.scrollIntoView({ block: "center" });
};

/** The rectangle of a place, moved up or down into the part of the window that the list takes. */
const getRectInListView = (place: HTMLElement) => {
  const rect = place.getBoundingClientRect();
  const view = (place.closest(".vertical-scrollbar") ?? document.body).getBoundingClientRect();
  return new DOMRect(
    rect.left,
    Math.max(view.top, Math.min(rect.top, view.bottom - rect.height)),
    rect.width,
    rect.height
  );
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
 * Sends a box from a rectangle to the place of a work item's line. The box starts as a picture, of the create
 * dialog or of the line where it was, takes the colour of the tint, and ends as the tinted line's picture exactly
 * over the line. The box is not part of the page: it takes no click and no key, and it goes by itself when its
 * time is over, whatever has become of the list meanwhile.
 *
 * A box at rest must lie on the line. The page may draw the line only later (the list had to scroll far, or has
 * just been given the line), and may be too busy with the list to do it in the box's time; the browser, which
 * moves the box without the page, would then leave it at rest where nobody has seen the line. And the place may
 * be one the list does not show: a line that went to another group is not scrolled to, and a folded group has
 * only its header to go to. So the box is set to go out as it arrives, at the edge of the list where its place
 * is beyond it, and stays whole only once the page has seen the line drawn, all of it in view.
 */
const sendBoxToLine = (workItemId: string, place: HTMLElement, from: DOMRect, picture: Node, isDialog: boolean) => {
  const box = document.createElement("div");
  box.className = isDialog ? MORPH_CLASS_NAME : `${MORPH_CLASS_NAME} ${MORPH_CLASS_NAME}-in-list`;
  box.inert = true;
  const surface = addLayer(box, "surface");
  surface.style.backgroundColor = TINT;
  const content = addLayer(box, "content");
  const dialogLayer = addLayer(content, "dialog", isDialog ? picture : undefined);
  const lineLayer = addLayer(content, "line", isDialog ? undefined : picture);
  Object.assign(dialogLayer.style, { width: `${from.width}px`, height: `${from.height}px` });
  document.body.append(box);

  const timing = { duration: MORPH_DURATION };
  const boxAnimation = box.animate(null, timing);
  const contentAnimation = content.animate(null, timing);
  if (isDialog) {
    // one picture leaves while the other comes, over the colour of the tint
    surface.animate({ opacity: [0, 1, 1], offset: [0, 0.2, 1] }, timing);
    dialogLayer.animate({ opacity: [1, 1, 0, 0], offset: [0, 0.1, 0.45, 1] }, timing);
    lineLayer.animate({ opacity: [0, 0, 1, 1], offset: [0, 0.35, 0.7, 1] }, timing);
  }
  const dissolve = box.animate(
    { opacity: [1, 1, 0], offset: [0, MORPH_DISSOLVE_START, 1] },
    { ...timing, fill: "forwards" }
  );
  let isLineDrawn = false;
  void boxAnimation.finished.then(() => {
    box.remove();
    // a line that was not drawn in the box's time gets its tint when it is
    return isLineDrawn ? undefined : highlightNewWorkItem(workItemId);
  });

  // The box sets off for the line's place at once and follows it from there. In a narrow window a line with many
  // values is higher than what stands in for it, so lines that the list draws meanwhile can still move this one,
  // also out of view again.
  let to: DOMRect | undefined;
  const followLine = () => {
    const line = place.querySelector<HTMLElement>(LINE_SELECTOR);
    const target = line ?? place;
    if (!box.isConnected || !target.isConnected) return;
    // only the line of a new work item is scrolled to
    if (isDialog) scrollListBlockIntoView(place);
    const isPlaceShown = isShownInList(place, true);
    if (line && !isLineDrawn) {
      isLineDrawn = true;
      highlightListLine(line);
      const lineCopy = line.cloneNode(true) as HTMLElement;
      lineCopy.style.backgroundColor = TINT;
      lineLayer.replaceChildren(lineCopy);
      // a box that has begun to go out goes on: coming back would flicker
      if (Number(boxAnimation.currentTime) < MORPH_DURATION * MORPH_DISSOLVE_START && isPlaceShown) dissolve.cancel();
    }
    // A place that the list shows whole is where the box goes, exactly: the last line of a list that is scrolled to
    // its end reaches a fraction of a pixel below the list's view, and a box kept inside the view would rest
    // beside that line.
    const rect = isPlaceShown ? target.getBoundingClientRect() : getRectInListView(target);
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

const isMotionReduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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
  if (isLineElsewhere && dialog && !isMotionReduced()) {
    const from = dialog.getBoundingClientRect();
    const picture = dialog.cloneNode(true);
    // The dialog leaves the page before the box enters it, so that each is the last child of the body when it goes
    // or comes: for a change among the body's children anywhere else the browser restyles the whole page.
    flushSync(close);
    block.animate({ opacity: [0, 0] }, MORPH_DURATION);
    sendBoxToLine(workItem.id, block, from, picture, true);
    return;
  }
  if (isLineElsewhere) scrollListBlockIntoView(block);
  close();
  if (!block) return;
  await highlightNewWorkItem(workItem.id);
  // the lines around it are drawn by now too; in a narrow window they may have pushed it out of view again
  if (isLineElsewhere) scrollListBlockIntoView(block);
};

/** The id of a group's header in the List layout: where a line goes whose new group is folded. */
export const getListGroupHeaderId = (groupId: string) => `list_group_header_${groupId}`;

/**
 * Points out a line that a change of its work item sends from one group of the list to another. It is to be
 * called when the change is made and the list has not drawn it yet: the line is then still at its old place.
 * From there a box in the line's look goes to the new place, and the line is tinted where it lands.
 *
 * Nothing scrolls, since the user did not ask to be taken anywhere. Without a line in view at the old place (the
 * change was made in the work item view while the list was scrolled elsewhere) there is nothing to set off from,
 * and a user who asked for reduced motion gets no box either: the line is only tinted.
 */
export const pointOutLineInNewGroup = async (workItemId: string, groupId: string, newGroupId: string) => {
  // A change from another session reaches a page that is not shown, too. The page would send the box when it is
  // shown again, from a place that is long gone.
  if (document.hidden) return;
  const line = document.getElementById(getIssueBlockId(workItemId, groupId))?.querySelector<HTMLElement>(LINE_SELECTOR);
  const start =
    line && isShownInList(line, false) && !isMotionReduced()
      ? { rect: line.getBoundingClientRect(), picture: line.cloneNode(true) as HTMLElement }
      : undefined;
  // the list draws the change
  await new Promise(requestAnimationFrame);
  const block = document.getElementById(getIssueBlockId(workItemId, newGroupId));
  const place = block ?? document.getElementById(getListGroupHeaderId(newGroupId));
  if (!start || !place) return highlightNewWorkItem(workItemId);
  start.picture.style.backgroundColor = TINT;
  block?.animate({ opacity: [0, 0] }, MORPH_DURATION);
  sendBoxToLine(workItemId, place, start.rect, start.picture, false);
};
