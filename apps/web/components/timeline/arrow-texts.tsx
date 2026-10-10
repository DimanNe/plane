/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { memo } from "react";
// plane imports
import type { TSchedule, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import type { TArrowWaysProps, TDrawnArrow, TPoint } from "./arrows";
import { getArrowLayerStyle, STUB } from "./arrows";
import { BAR_HEIGHT, BAR_TOP, DATE_DISTANCE, DATE_WIDTH } from "./bar";
import type { TTimelineView } from "./scale";
import { getDayDistance, MIN_BAR_WIDTH } from "./scale";

type TRect = { left: number; top: number; right: number; bottom: number };

type TArrowText = { look: "set" | "gap" | "conflict"; days: number };

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
  onClick: (arrow: TScheduleArrow) => void;
  onHover: (arrow: TScheduleArrow | undefined) => void;
};

// The size a text takes on the timeline, for finding it a free place. A little less than it is drawn with, so
// that a text may touch a bar.
const TEXT_HEIGHT = 12;
const CHARACTER_WIDTH = 6;
// how far along its arrow from the middle a text goes for a free place, and in what steps
const TEXT_REACH = 240;
const TEXT_STEP = 8;
const CLASS_NAMES = {
  set: "text-caption-md-medium text-secondary",
  gap: "text-caption-md-regular text-placeholder",
  conflict: "text-caption-md-medium text-danger-primary",
};

/**
 * What an arrow says over itself, always: nothing when its next task follows it "immediately", the days of a set
 * delay, the days there are to a task that is fixed on its day (nobody set them, so they read fainter), and for a
 * conflict the days by which the fixed task is too early for the arrow.
 */
const getArrowText = (arrow: TScheduleArrow, schedule: TSchedule, isNextFixed: boolean): TArrowText | undefined => {
  const gap = schedule.gaps[arrow.id];
  if (gap === undefined) return;
  if (!isNextFixed) return arrow.delay ? { look: "set", days: arrow.delay } : undefined;
  if (schedule.conflicts.some((conflict) => conflict.arrowId === arrow.id))
    return { look: "conflict", days: arrow.delay - gap };
  return gap ? { look: "gap", days: gap } : undefined;
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
const getTextPlace = (points: TPoint[], width: number, takenRects: TRect[], viewTop: number, viewBottom: number) => {
  const length = getLength(points);
  const getRect = ([x, y]: TPoint): TRect => ({
    left: x - width / 2,
    top: y - TEXT_HEIGHT / 2,
    right: x + width / 2,
    bottom: y + TEXT_HEIGHT / 2,
  });
  let freePlace: TPoint | undefined;
  for (let offset = 0; offset <= TEXT_REACH; offset += TEXT_STEP)
    for (const distance of offset ? [length / 2 + offset, length / 2 - offset] : [length / 2]) {
      if (distance < STUB || distance > length - STUB) continue;
      const place = getPointAt(points, distance);
      const rect = getRect(place);
      if (takenRects.some((taken) => isOver(rect, taken))) continue;
      if (place[1] >= viewTop && place[1] <= viewBottom) return { place, rect };
      freePlace ??= place;
    }
  const place = freePlace ?? getPointAt(points, length / 2);
  return { place, rect: getRect(place) };
};

const ArrowTexts = memo(function ArrowTexts(props: Props) {
  const { drawnArrows, schedule, followingTaskIds, viewTop, viewBottom, onClick, onHover } = props;
  // translation
  const { t } = useTranslation();
  // a text that has its place is in the way of the next ones
  const takenRects = getTakenRects(props);

  return drawnArrows.map(({ arrow, points }) => {
    const arrowText = getArrowText(arrow, schedule, !followingTaskIds.has(arrow.nextId));
    if (!arrowText) return null;
    const text = t(`timeline.arrow.${arrowText.look === "conflict" ? "too_early" : "in_days"}`, {
      days: arrowText.days,
    });
    const { place, rect } = getTextPlace(points, (text.length + 2) * CHARACTER_WIDTH, takenRects, viewTop, viewBottom);
    takenRects.push(rect);
    return (
      <button
        key={arrow.id}
        type="button"
        className={cn(
          "pointer-events-auto absolute h-4 -translate-x-1/2 -translate-y-1/2 cursor-pointer rounded-sm bg-surface-1 px-1 whitespace-nowrap",
          CLASS_NAMES[arrowText.look]
        )}
        style={{ left: place[0], top: place[1] }}
        onClick={() => onClick(arrow)}
        onPointerEnter={() => onHover(arrow)}
        onPointerLeave={() => onHover(undefined)}
      >
        {text}
      </button>
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
