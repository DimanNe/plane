/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { clamp } from "lodash-es";
// local imports
import { trackPointer } from "./pointer";
import type { TTimelineView } from "./scale";
import { MAX_PX_PER_DAY, MIN_PX_PER_DAY } from "./scale";

// one notch of a mouse wheel is 100 pixels: a sixth more or less of everything
const ZOOM_PER_WHEEL_PIXEL = 0.0015;
// a pinch on a touchpad comes as a wheel with Ctrl and far smaller steps
const ZOOM_PER_PINCH_PIXEL = 0.01;
const MAX_ZOOM_PER_EVENT = 0.5;
// the scale reaches the one the wheel asked for over a few frames, so a notch is seen as a movement
const ZOOM_EASING_MS = 60;
const WHEEL_LINE_HEIGHT = 16;

type TZoomTarget = { pxPerDay: number; x: number; day: number };

type TTimelineSpan = Pick<TTimelineView, "originDay" | "pxPerDay">;

/**
 * The part of time the timeline shows. The wheel changes the scale around the day under the pointer, a drag
 * of empty space moves the time and scrolls the lines; a press there that does not move is `onClick`.
 * @param scroll the element that scrolls the lines and holds the list beside the timeline
 * @param canvas the element as wide as the timeline, to the right of the list
 */
export const useTimelineView = (
  scroll: HTMLElement | null,
  canvas: HTMLElement | null,
  getInitialView: (width: number) => TTimelineSpan,
  onClick: (position: { clientX: number; clientY: number }) => void
) => {
  // states
  const [span, setSpan] = useState<TTimelineSpan>();
  const [width, setWidth] = useState(0);
  const [isPanning, setIsPanning] = useState(false);
  // refs
  const viewRef = useRef<TTimelineSpan>(undefined);
  const zoomTargetRef = useRef<TZoomTarget>(undefined);
  const frameRef = useRef<{ id: number; time?: number }>(undefined);

  const showView = useCallback(({ originDay, pxPerDay }: TTimelineSpan) => {
    viewRef.current = { originDay, pxPerDay };
    setSpan(viewRef.current);
  }, []);

  useLayoutEffect(() => {
    if (!canvas) return;
    // full screen draws the timeline in other elements, with the view it has
    if (!viewRef.current) showView(getInitialView(canvas.clientWidth));
    setWidth(canvas.clientWidth);
    const observer = new ResizeObserver(() => setWidth(canvas.clientWidth));
    observer.observe(canvas);
    return () => observer.disconnect();
    // the view is chosen once, for the bars the timeline opens with
    // oxlint-disable-next-line eslint-plugin-react-hooks/exhaustive-deps
  }, [canvas, showView]);

  const zoomTo = useCallback(
    (pxPerDay: number, x: number) => {
      const current = viewRef.current;
      if (!current) return;
      zoomTargetRef.current = {
        pxPerDay: clamp(pxPerDay, MIN_PX_PER_DAY, MAX_PX_PER_DAY),
        x,
        day: current.originDay + x / current.pxPerDay,
      };
      if (frameRef.current) return;

      const showNextFrame = (time: number) => {
        const target = zoomTargetRef.current;
        const shown = viewRef.current;
        if (!target || !shown) {
          frameRef.current = undefined;
          return;
        }
        const elapsed = time - (frameRef.current?.time ?? time - 1000 / 60);
        const remaining = Math.log(target.pxPerDay / shown.pxPerDay) * Math.exp(-elapsed / ZOOM_EASING_MS);
        const isReached = Math.abs(remaining) < 0.002;
        const nextPxPerDay = isReached ? target.pxPerDay : target.pxPerDay / Math.exp(remaining);
        // the day under the pointer stays under the pointer
        showView({ pxPerDay: nextPxPerDay, originDay: target.day - target.x / nextPxPerDay });
        frameRef.current = isReached ? undefined : { id: requestAnimationFrame(showNextFrame), time };
        if (isReached) zoomTargetRef.current = undefined;
      };
      frameRef.current = { id: requestAnimationFrame(showNextFrame) };
    },
    [showView]
  );

  useEffect(() => () => cancelAnimationFrame(frameRef.current?.id ?? 0), []);

  // React listens to the wheel passively, and a passive listener cannot keep the page from scrolling
  useEffect(() => {
    if (!scroll || !canvas) return;
    const handleWheel = (event: WheelEvent) => {
      const current = viewRef.current;
      const x = event.clientX - canvas.getBoundingClientRect().left;
      // over the list the wheel scrolls the lines
      if (!current || x < 0) return;
      event.preventDefault();
      const unit = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? WHEEL_LINE_HEIGHT : 1;
      // a sideways wheel, or two fingers moved sideways, pans
      if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) {
        zoomTargetRef.current = undefined;
        showView({ ...current, originDay: current.originDay + (event.deltaX * unit) / current.pxPerDay });
        return;
      }
      const targetPxPerDay = zoomTargetRef.current?.pxPerDay ?? current.pxPerDay;
      const zoom = -event.deltaY * unit * (event.ctrlKey ? ZOOM_PER_PINCH_PIXEL : ZOOM_PER_WHEEL_PIXEL);
      zoomTo(targetPxPerDay * Math.exp(clamp(zoom, -MAX_ZOOM_PER_EVENT, MAX_ZOOM_PER_EVENT)), x);
    };
    scroll.addEventListener("wheel", handleWheel, { passive: false });
    return () => scroll.removeEventListener("wheel", handleWheel);
  }, [scroll, canvas, showView, zoomTo]);

  const handlePointerDown = (press: React.PointerEvent) => {
    if (!scroll || !canvas || press.button !== 0 || press.clientX < canvas.getBoundingClientRect().left) return;
    zoomTargetRef.current = undefined;
    const scrollTop = scroll.scrollTop;
    let lastClientX = press.clientX;
    trackPointer(press, {
      onMove: ({ clientX, clientY }) => {
        const current = viewRef.current;
        if (!current) return;
        setIsPanning(true);
        // step by step: the wheel may change the scale while the pointer is down
        showView({ ...current, originDay: current.originDay - (clientX - lastClientX) / current.pxPerDay });
        lastClientX = clientX;
        scroll.scrollTop = scrollTop - (clientY - press.clientY);
      },
      onEnd: ({ isDragged, isAborted }) => {
        setIsPanning(false);
        if (!isDragged && !isAborted) onClick(press);
      },
    });
  };

  /** The day at a place of the window, with the part of the day that lies before that place. */
  const getDayAt = useCallback(
    (clientX: number) => {
      const current = viewRef.current;
      return current && canvas
        ? current.originDay + (clientX - canvas.getBoundingClientRect().left) / current.pxPerDay
        : 0;
    },
    [canvas]
  );

  const view: TTimelineView | undefined = useMemo(() => span && { ...span, width }, [span, width]);

  return { view, isPanning, showView, getDayAt, handlePointerDown };
};
