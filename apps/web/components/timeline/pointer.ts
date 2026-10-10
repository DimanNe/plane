/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// a pointer that stays this near to where it was pressed has not moved: the press is a click
const DRAG_THRESHOLD = 4;

type TPointerPosition = { clientX: number; clientY: number };

type TPointerHandlers = {
  /** The pointer has left the place of the press. `axis` is the direction of its first movement and stays. */
  onMove: (position: TPointerPosition, axis: "x" | "y") => void;
  /**
   * The pointer is released, or the press is aborted: by Escape, or because its release cannot reach the page any
   * more. Every press ends once. A press that never moved and was not aborted is a click.
   */
  onEnd: (result: { isDragged: boolean; isAborted: boolean }) => void;
};

const stopEvent = (event: Event) => {
  event.stopPropagation();
  event.preventDefault();
};

// the click the browser sends after the release belongs to the drag, not to what the pointer is over
const swallowNextClick = () => {
  document.addEventListener("click", stopEvent, { capture: true, once: true });
  setTimeout(() => document.removeEventListener("click", stopEvent, true));
};

/** Follows the pointer from a press until its release. */
export const trackPointer = (press: TPointerPosition, handlers: TPointerHandlers) => {
  let axis: "x" | "y" | undefined;

  const handleMove = (event: PointerEvent) => {
    // no button is down any more: the release happened where the page did not get it
    if (event.buttons === 0) return end(true);
    const distanceX = Math.abs(event.clientX - press.clientX);
    const distanceY = Math.abs(event.clientY - press.clientY);
    if (!axis && Math.max(distanceX, distanceY) < DRAG_THRESHOLD) return;
    axis ??= distanceX >= distanceY ? "x" : "y";
    handlers.onMove(event, axis);
  };
  const end = (isAborted: boolean) => {
    document.removeEventListener("pointermove", handleMove);
    document.removeEventListener("pointerup", handleRelease);
    document.removeEventListener("pointercancel", handleAbort);
    window.removeEventListener("blur", handleAbort);
    document.removeEventListener("keydown", handleKeyDown, true);
    if (isAborted) document.addEventListener("pointerup", swallowNextClick, { once: true });
    else if (axis) swallowNextClick();
    handlers.onEnd({ isDragged: !!axis, isAborted });
  };
  const handleRelease = () => end(false);
  const handleAbort = () => end(true);
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key !== "Escape") return;
    // Escape ends the drag and nothing else: it would also close the work item view beside the timeline
    stopEvent(event);
    end(true);
  };

  document.addEventListener("pointermove", handleMove);
  document.addEventListener("pointerup", handleRelease);
  document.addEventListener("pointercancel", handleAbort);
  // in another window the pointer can be released without a word to this one
  window.addEventListener("blur", handleAbort);
  document.addEventListener("keydown", handleKeyDown, true);
};
