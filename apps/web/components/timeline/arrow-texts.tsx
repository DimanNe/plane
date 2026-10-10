/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { memo, useEffect, useRef, useState } from "react";
// plane imports
import { changeArrow } from "@plane/blocks/timeline-schedule";
import type { TPlan, TSchedule, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { useLatestCallback } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import type { TArrowWaysProps, TDrawnArrow, TPoint } from "./arrows";
import { getArrowLayerStyle, STUB } from "./arrows";
import { BAR_HEIGHT, BAR_TOP, DATE_DISTANCE, DATE_WIDTH } from "./bar";
import type { TTimelineOperation } from "./operation";
import type { TTimelineView } from "./scale";
import { getDayDistance, MIN_BAR_WIDTH } from "./scale";
import { useWheelNotches } from "./wheel";

type TRect = { left: number; top: number; right: number; bottom: number };

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
  operation: TTimelineOperation;
  isEditable: boolean;
  onClick: (arrow: TScheduleArrow, click: React.MouseEvent) => void;
  onHover: (arrow: TScheduleArrow | undefined) => void;
};

// The size a text takes on the timeline, for finding it a free place. A little less than it is drawn with, so
// that a text may touch a bar.
const TEXT_HEIGHT = 12;
const CHARACTER_WIDTH = 6;
// how far along its arrow from the middle a text goes for a free place, and in what steps
const TEXT_REACH = 240;
const TEXT_STEP = 8;
// how long the wheel rests over a text before what it changed is saved
const WHEEL_REST_TIME = 800;
const CLASS_NAMES = {
  delay: "text-secondary",
  conflict: "text-danger-primary",
};

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

/**
 * The wheel over the text of an arrow changes the delay of the arrow, a day a notch. That is one operation: begun
 * at the first notch, shown at every notch, and saved when the wheel has rested for a moment or the pointer has
 * left the text; Escape drops it. It never stays open: changes of the plan made elsewhere wait for its end.
 */
const useDelayByWheel = (operation: TTimelineOperation) => {
  // the operation that is going on: the arrow, the plan it began with, and the timer of the rest
  const turnRef = useRef<{ arrowId: string; plan: TPlan; timer: number }>(undefined);

  const end = useLatestCallback((isAborted: boolean) => {
    const turn = turnRef.current;
    if (!turn) return;
    turnRef.current = undefined;
    window.clearTimeout(turn.timer);
    document.removeEventListener("keydown", handleKeyDown, true);
    if (isAborted) operation.abort();
    else operation.commit();
  });

  const handleKeyDown = useLatestCallback((event: KeyboardEvent) => {
    if (event.key !== "Escape") return;
    // Escape ends the operation and nothing else
    event.stopPropagation();
    event.preventDefault();
    end(true);
  });

  const turn = useLatestCallback((arrow: TScheduleArrow, direction: 1 | -1) => {
    if (turnRef.current && turnRef.current.arrowId !== arrow.id) end(false);
    if (!turnRef.current) {
      const plan = operation.begin();
      if (!plan) return;
      turnRef.current = { arrowId: arrow.id, plan, timer: 0 };
      document.addEventListener("keydown", handleKeyDown, true);
    }
    window.clearTimeout(turnRef.current.timer);
    turnRef.current.timer = window.setTimeout(() => end(false), WHEEL_REST_TIME);
    operation.preview(changeArrow(turnRef.current.plan, arrow.id, { delay: Math.max(arrow.delay + direction, 1) }));
  });

  useEffect(() => () => end(true), [end]);

  return { turn, end };
};

type TTextProps = {
  arrow: TScheduleArrow;
  text: string;
  look: TArrowText["look"];
  place: TPoint;
  onClick: (arrow: TScheduleArrow, click: React.MouseEvent) => void;
  onPointerEnter: (arrow: TScheduleArrow, place: TPoint) => void;
  onPointerLeave: () => void;
  // the wheel over the text turns the delay of its arrow; not given where the wheel does what it does elsewhere
  onWheelNotch: ((arrow: TScheduleArrow, direction: 1 | -1) => void) | undefined;
};

function ArrowText(props: TTextProps) {
  const { arrow, text, look, place, onClick, onPointerEnter, onPointerLeave, onWheelNotch } = props;
  // states
  const [element, setElement] = useState<HTMLButtonElement | null>(null);

  useWheelNotches(element, onWheelNotch && ((direction) => onWheelNotch(arrow, direction)));

  return (
    <button
      ref={setElement}
      type="button"
      className={cn(
        "pointer-events-auto absolute h-4 -translate-x-1/2 -translate-y-1/2 cursor-pointer rounded-sm bg-surface-1 px-1 text-caption-md-medium whitespace-nowrap",
        CLASS_NAMES[look]
      )}
      style={{ left: place[0], top: place[1] }}
      onClick={(e) => onClick(arrow, e)}
      onPointerEnter={() => onPointerEnter(arrow, place)}
      onPointerLeave={onPointerLeave}
    >
      {text}
    </button>
  );
}

const ArrowTexts = memo(function ArrowTexts(props: Props) {
  const { drawnArrows, schedule, followingTaskIds, viewTop, viewBottom, operation, isEditable, onClick, onHover } =
    props;
  // states
  // The text the pointer is over, and its place. It stays there while the pointer is on it, whatever its arrow
  // does: a text that moved away from under the pointer would have to be found again.
  const [held, setHeld] = useState<{ arrowId: string; place: TPoint }>();
  // translation
  const { t } = useTranslation();
  // hooks
  const { turn, end } = useDelayByWheel(operation);

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

  // a text that went away under the pointer tells nobody that the pointer has left it
  const isHeldTextGone = !!held && !heldText;
  useEffect(() => {
    if (isHeldTextGone) setHeld(undefined);
  }, [isHeldTextGone]);

  return texts.map(({ arrow, points, text, look, width }) => {
    const place =
      held && arrow.id === held.arrowId ? held.place : getTextPlace(points, width, takenRects, viewTop, viewBottom);
    if (arrow.id !== held?.arrowId) takenRects.push(getTextRect(place, width));
    return (
      <ArrowText
        key={arrow.id}
        arrow={arrow}
        text={text}
        look={look}
        place={place}
        onClick={(clickedArrow, click) => {
          end(false);
          onClick(clickedArrow, click);
        }}
        onPointerEnter={(enteredArrow, enteredPlace) => {
          setHeld({ arrowId: enteredArrow.id, place: enteredPlace });
          onHover(enteredArrow);
        }}
        onPointerLeave={() => {
          end(false);
          setHeld(undefined);
          onHover(undefined);
        }}
        onWheelNotch={isEditable && look === "delay" ? turn : undefined}
      />
    );
  });
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
