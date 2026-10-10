/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { minBy } from "lodash-es";
import { memo, useEffect, useRef, useState } from "react";
// plane imports
import { changeArrow } from "@plane/blocks/timeline-schedule";
import type { TSchedule, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { useLatestCallback } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";
// components
import { BLOCK_HEIGHT, HEADER_HEIGHT, SIDEBAR_WIDTH } from "@/components/gantt-chart/constants";
// local imports
import type { TArrowWaysProps, TDrawnArrow, TPoint } from "./arrows";
import { getArrowLayerStyle, STUB } from "./arrows";
import { BAR_HEIGHT, BAR_TOP, DATE_DISTANCE, DATE_WIDTH } from "./bar";
import type { TTimelineView } from "./scale";
import { getDayDistance, MIN_BAR_WIDTH } from "./scale";
import { TimelineText, TimelineTextPart } from "./text";
import type { TWheelTurn } from "./use-wheel-turn";
import { useWheelNotches } from "./wheel";

type TRect = { left: number; top: number; right: number; bottom: number };

type TPosition = { clientX: number; clientY: number; target?: EventTarget | null };

type TArrowText = { look: "delay" | "conflict"; days: number };

type Props = Omit<TArrowWaysProps, "arrows"> & {
  drawnArrows: TDrawnArrow[];
  schedule: TSchedule;
  // the tasks that follow their arrows; the others are fixed on a day
  followingTaskIds: Set<string>;
  // the fixed tasks that show the date of their start beside their bar
  datedTaskIds: Set<string>;
  // the lines in view, in pixels from the top of the first line
  viewTop: number;
  viewBottom: number;
  wheelTurn: TWheelTurn;
  isEditable: boolean;
  // the element that scrolls the lines of the timeline
  scroll: HTMLElement | null;
  onClick: (arrow: TScheduleArrow, click: React.MouseEvent) => void;
  onHover: (arrow: TScheduleArrow | undefined) => void;
};

// The size a text takes on the timeline, for finding it a free place. A little less than it is drawn with, so
// that a text may touch a bar.
const TEXT_HEIGHT = 16;
const CHARACTER_WIDTH = 6;
// how far along its arrow from the middle a text goes for a free place, and in what steps
const TEXT_REACH = 240;
const TEXT_STEP = 8;
// How far around a text that shows a delay the wheel still turns that delay: about a centimetre, by which a hand
// that aims at a small text misses it.
const WHEEL_MARGIN = 36;

/**
 * What an arrow says over itself, always: the days of its delay when its next task follows it with one, and for
 * a conflict the days by which the fixed task is too early for the arrow. Else nothing: an arrow that is
 * followed "immediately" needs no word, and of a task that is fixed on its day the date stands beside its bar.
 */
const getArrowText = (arrow: TScheduleArrow, schedule: TSchedule, isNextFixed: boolean): TArrowText | undefined => {
  const gap = schedule.gaps[arrow.id];
  if (gap === undefined) return;
  if (!isNextFixed) return arrow.delay ? { look: "delay", days: arrow.delay } : undefined;
  if (schedule.conflicts.some((conflict) => conflict.arrowId === arrow.id))
    return { look: "conflict", days: arrow.delay - gap };
};

/** The point of a way through the points that is at a distance from its start. */
const getPointAt = (points: TPoint[], distance: number): TPoint => {
  let rest = distance;
  for (let index = 1; index < points.length; index++) {
    const [x, y] = points[index - 1];
    const [nextX, nextY] = points[index];
    const length = Math.abs(nextX - x) + Math.abs(nextY - y);
    if (rest <= length) return [x + ((nextX - x) * rest) / (length || 1), y + ((nextY - y) * rest) / (length || 1)];
    rest -= length;
  }
  return points[points.length - 1];
};

const getLength = (points: TPoint[]) =>
  points
    .slice(1)
    .reduce((length, [x, y], index) => length + Math.abs(x - points[index][0]) + Math.abs(y - points[index][1]), 0);

const isOver = (a: TRect, b: TRect) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

/** What a text of a width takes when it stands with its middle at a place. */
const getTextRect = ([x, y]: TPoint, width: number): TRect => ({
  left: x - width / 2,
  top: y - TEXT_HEIGHT / 2,
  right: x + width / 2,
  bottom: y + TEXT_HEIGHT / 2,
});

/** What a text keeps clear of: the bars of the lines that are drawn, and the dates beside fixed tasks. */
const getTakenRects = (props: Props): TRect[] => {
  const { days, lineIndexes, firstLine, lastLine, pxPerDay, datedTaskIds } = props;
  const rects: TRect[] = [];
  for (const [taskId, lineIndex] of lineIndexes) {
    const task = days[taskId];
    if (!task || lineIndex < firstLine - 1 || lineIndex > lastLine) continue;
    const left = getDayDistance(pxPerDay, task.start);
    const right = Math.max(getDayDistance(pxPerDay, task.end + 1), left + MIN_BAR_WIDTH);
    const top = lineIndex * BLOCK_HEIGHT + BAR_TOP;
    const dateWidth = datedTaskIds.has(taskId) ? DATE_DISTANCE + DATE_WIDTH : 0;
    rects.push({ left: left - dateWidth, top, right, bottom: top + BAR_HEIGHT });
  }
  return rects;
};

/**
 * The place of a text on its arrow: as near to the middle of the arrow as a place is free, and clear of the ends
 * of the arrow, where the handles are. A place among the lines in view goes before one that is not; where no
 * place is free the text stands in the middle.
 */
const getTextPlace = (
  points: TPoint[],
  width: number,
  takenRects: TRect[],
  viewTop: number,
  viewBottom: number
): TPoint => {
  const length = getLength(points);
  let freePlace: TPoint | undefined;
  for (let offset = 0; offset <= TEXT_REACH; offset += TEXT_STEP)
    for (const distance of offset ? [length / 2 + offset, length / 2 - offset] : [length / 2]) {
      if (distance < STUB || distance > length - STUB) continue;
      const place = getPointAt(points, distance);
      const rect = getTextRect(place, width);
      if (takenRects.some((taken) => isOver(rect, taken))) continue;
      if (place[1] >= viewTop && place[1] <= viewBottom) return place;
      freePlace ??= place;
    }
  return freePlace ?? getPointAt(points, length / 2);
};

type TTextProps = {
  ref: (element: HTMLElement | null) => void;
  arrow: TScheduleArrow;
  text: string;
  look: TArrowText["look"];
  place: TPoint;
  // a click on it opens the control of its arrow, and the wheel turns a delay
  isActionable: boolean;
  isHeld: boolean;
  onClick: (arrow: TScheduleArrow, click: React.MouseEvent) => void;
  onHover: (arrow: TScheduleArrow | undefined) => void;
};

function ArrowText(props: TTextProps) {
  const { ref, arrow, text, look, place, isActionable, isHeld, onClick, onHover } = props;

  return (
    <TimelineText
      ref={ref}
      isDanger={look === "conflict"}
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{ left: place[0], top: place[1] }}
    >
      <TimelineTextPart
        isActionable={isActionable}
        isHeld={isHeld}
        onClick={(e) => onClick(arrow, e)}
        onPointerEnter={() => onHover(arrow)}
        onPointerLeave={() => onHover(undefined)}
      >
        {text}
      </TimelineTextPart>
    </TimelineText>
  );
}

const ArrowTexts = memo(function ArrowTexts(props: Props) {
  const {
    drawnArrows,
    schedule,
    followingTaskIds,
    viewTop,
    viewBottom,
    wheelTurn,
    isEditable,
    scroll,
    onClick,
    onHover,
  } = props;
  // refs
  const elementsRef = useRef(new Map<string, HTMLElement>());
  // states
  // The text whose area the pointer is in, and its place. It stays there while the pointer is in the area,
  // whatever its arrow does: a text that moved away from the pointer would have to be found again.
  const [held, setHeld] = useState<{ arrowId: string; place: TPoint }>();
  // translation
  const { t } = useTranslation();

  const texts = drawnArrows.flatMap(({ arrow, points }) => {
    const arrowText = getArrowText(arrow, schedule, !followingTaskIds.has(arrow.nextId));
    if (!arrowText) return [];
    const text = t(`timeline.arrow.${arrowText.look === "conflict" ? "too_early" : "in_days"}`, {
      days: arrowText.days,
    });
    return [{ arrow, points, text, look: arrowText.look, width: (text.length + 2) * CHARACTER_WIDTH }];
  });
  // A text that has its place is in the way of the next ones: first the one the pointer holds, then the others.
  const takenRects = getTakenRects(props);
  const heldText = texts.find(({ arrow }) => arrow.id === held?.arrowId);
  if (held && heldText) takenRects.push(getTextRect(held.place, heldText.width));
  const placedTexts = texts.map(({ arrow, points, text, look, width }) => {
    const place =
      held && arrow.id === held.arrowId ? held.place : getTextPlace(points, width, takenRects, viewTop, viewBottom);
    if (arrow.id !== held?.arrowId) takenRects.push(getTextRect(place, width));
    return { arrow, text, look, place };
  });

  /** The arrow whose delay the wheel is turning; nothing while it turns something else of the timeline. */
  const getTurnedArrowId = () => {
    const turnedKey = wheelTurn.getTurnedKey();
    return placedTexts.some(({ arrow }) => arrow.id === turnedKey) ? turnedKey : undefined;
  };

  /**
   * The text that has a place of the window in its area; of several the nearest. The area of a text that shows a
   * delay is the text and `WHEEL_MARGIN` on every side of it: there the wheel turns the delay. The area of
   * another text is the text. A text whose delay is being turned keeps the wheel while the place is in its area:
   * its bars move, and another text may come nearer. Where the pointer is on something else that takes the wheel,
   * that has it.
   */
  const getTextNear = ({ clientX, clientY, target }: TPosition) => {
    if (!isEditable || !scroll) return;
    const part = target instanceof Element ? target.closest("[data-actionable]") : null;
    if (part && ![...elementsRef.current.values()].some((element) => element.contains(part))) return;
    const frame = scroll.getBoundingClientRect();
    // the list and the header of the timeline cover what is under them
    if (clientX < frame.left + SIDEBAR_WIDTH || clientY < frame.top + HEADER_HEIGHT) return;
    const textsNear = placedTexts.flatMap((placedText) => {
      const box = elementsRef.current.get(placedText.arrow.id)?.getBoundingClientRect();
      if (!box) return [];
      const margin = placedText.look === "delay" ? WHEEL_MARGIN : 0;
      const distanceX = Math.max(box.left - clientX, clientX - box.right, 0);
      const distanceY = Math.max(box.top - clientY, clientY - box.bottom, 0);
      if (distanceX > margin || distanceY > margin) return [];
      return [{ ...placedText, distance: Math.hypot(distanceX, distanceY) }];
    });
    return textsNear.find(({ arrow }) => arrow.id === getTurnedArrowId()) ?? minBy(textsNear, "distance");
  };

  /** Holds the text that has the pointer in its area, and saves what the wheel turned on the one it has left. */
  const holdTextNear = useLatestCallback((position: TPosition | undefined) => {
    const textNear = position && getTextNear(position);
    const turnedArrowId = getTurnedArrowId();
    if (turnedArrowId && textNear?.arrow.id !== turnedArrowId) wheelTurn.end(false);
    if (textNear?.arrow.id !== held?.arrowId)
      setHeld(textNear && { arrowId: textNear.arrow.id, place: textNear.place });
    return textNear;
  });

  useEffect(() => {
    if (!scroll) return;
    const handlePointerLeave = () => holdTextNear(undefined);
    scroll.addEventListener("pointermove", holdTextNear);
    scroll.addEventListener("pointerleave", handlePointerLeave);
    return () => {
      scroll.removeEventListener("pointermove", holdTextNear);
      scroll.removeEventListener("pointerleave", handlePointerLeave);
    };
  }, [scroll, holdTextNear]);

  useWheelNotches(
    scroll,
    (direction, event) => {
      const textNear = holdTextNear(event);
      const arrow = textNear?.arrow;
      if (arrow)
        wheelTurn.turn(arrow.id, (plan) =>
          changeArrow(plan, arrow.id, { delay: Math.max(arrow.delay + direction, 1) })
        );
    },
    (event) => holdTextNear(event)?.look === "delay"
  );

  // a text that went away with the pointer in its area tells nobody that the pointer has left it
  const isHeldTextGone = !!held && !heldText;
  useEffect(() => {
    if (isHeldTextGone) setHeld(undefined);
  }, [isHeldTextGone]);

  return placedTexts.map(({ arrow, text, look, place }) => (
    <ArrowText
      key={arrow.id}
      ref={(element) => {
        if (element) elementsRef.current.set(arrow.id, element);
        return () => {
          elementsRef.current.delete(arrow.id);
        };
      }}
      arrow={arrow}
      text={text}
      look={look}
      place={place}
      isActionable={isEditable}
      isHeld={isEditable && arrow.id === held?.arrowId}
      onClick={(clickedArrow, click) => {
        wheelTurn.end(false);
        onClick(clickedArrow, click);
      }}
      onHover={onHover}
    />
  ));
});

/** The texts over the arrows: how each arrow is set, without a click. */
export function TimelineArrowTexts(props: Omit<Props, "pxPerDay"> & { view: TTimelineView }) {
  const { view, ...textsProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getArrowLayerStyle(view)}>
      <ArrowTexts pxPerDay={view.pxPerDay} {...textsProps} />
    </div>
  );
}
