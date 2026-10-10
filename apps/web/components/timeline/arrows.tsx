/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { memo } from "react";
import { clamp } from "lodash-es";
// plane imports
import type { TSchedule, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { cn } from "@plane/utils";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import type { TTimelineView } from "./scale";
import { BASE_DAY, getDayDistance, getDayX, MIN_BAR_WIDTH } from "./scale";

export type TPoint = [x: number, y: number];

/** An end of an arrow: its tail is at the previous task, its head at the next one. */
export type TArrowEnd = "tail" | "head";

// what the way of an arrow depends on
export type TArrowWaysProps = {
  arrows: TScheduleArrow[];
  // the first and the last day of every task that has a bar
  days: Record<string, { start: number; end: number }>;
  lineIndexes: Map<string, number>;
  // the lines that are drawn
  firstLine: number;
  lastLine: number;
  pxPerDay: number;
};

type TPathsProps = TArrowWaysProps & {
  schedule: TSchedule;
  selectedArrowId: string | undefined;
  // the arrows that produce the conflict the pointer is over
  causeArrowIds: string[];
  isEditable: boolean;
  onClick: (arrow: TScheduleArrow) => void;
  onHover: (arrow: TScheduleArrow | undefined) => void;
  onEndPress: (press: React.PointerEvent, arrow: TScheduleArrow, end: TArrowEnd) => void;
};

/**
 * Where the bar of the next task is, seen from the place of an arrow's control: to the right of the arrow or to
 * its left, under it or above. What opens at the control opens away from that bar.
 */
export type TNextTaskSide = { isRight: boolean; isBelow: boolean };

type TControlsProps = TArrowWaysProps & {
  // the lines in view, in pixels from the top of the first line
  viewTop: number;
  viewBottom: number;
  renderControl: (arrow: TScheduleArrow, nextTaskSide: TNextTaskSide) => ReactNode;
};

// how far an arrow runs straight out of a bar and into one: past the handle at that end of the bar
export const STUB = 18;
const CORNER_RADIUS = 5;
// the colour of an arrow: of a conflict and of what produces it, of a critical or a selected arrow, of the others
const CLASS_NAMES = {
  normal: "text-placeholder",
  accent: "text-accent-primary",
  danger: "text-danger-primary",
};

/** A line through the points with its corners rounded. */
const getPath = (points: TPoint[]) => {
  const getPointTowards = ([x, y]: TPoint, [toX, toY]: TPoint) => {
    const length = Math.abs(toX - x) + Math.abs(toY - y) || 1;
    const radius = Math.min(CORNER_RADIUS, length / 2);
    return [x + ((toX - x) / length) * radius, y + ((toY - y) / length) * radius];
  };
  const corners = points
    .slice(1, -1)
    .map(
      (corner, index) =>
        `L ${getPointTowards(corner, points[index])} Q ${corner} ${getPointTowards(corner, points[index + 2])}`
    );
  return `M ${points[0]} ${corners.join(" ")} L ${points[points.length - 1]}`;
};

/**
 * The way of an arrow from the bar of the previous task to the bar of the next one: out of the end or the start
 * it constrains by, along the lines, into the start or the end it constrains.
 */
const getPoints = (arrow: TScheduleArrow, props: TArrowWaysProps): TPoint[] | undefined => {
  const { days, lineIndexes, firstLine, lastLine, pxPerDay } = props;
  const previous = days[arrow.previousId];
  const next = days[arrow.nextId];
  const previousLine = lineIndexes.get(arrow.previousId);
  const nextLine = lineIndexes.get(arrow.nextId);
  if (!previous || !next || previousLine === undefined || nextLine === undefined) return;
  // both of its bars are above the lines that are drawn, or both below
  if (Math.max(previousLine, nextLine) < firstLine || Math.min(previousLine, nextLine) >= lastLine) return;

  const getStartX = (task: { start: number }) => getDayDistance(pxPerDay, task.start);
  const getEndX = (task: { start: number; end: number }) =>
    Math.max(getDayDistance(pxPerDay, task.end + 1), getStartX(task) + MIN_BAR_WIDTH);
  const fromX = arrow.kind === "start-start" ? getStartX(previous) : getEndX(previous);
  const toX = arrow.kind === "end-end" ? getEndX(next) : getStartX(next);
  const fromY = (previousLine + 0.5) * BLOCK_HEIGHT;
  const toY = (nextLine + 0.5) * BLOCK_HEIGHT;

  if (arrow.kind !== "end-start") {
    // around the starts on their left, around the ends on their right
    const turnX = arrow.kind === "start-start" ? Math.min(fromX, toX) - STUB : Math.max(fromX, toX) + STUB;
    return [
      [fromX, fromY],
      [turnX, fromY],
      [turnX, toY],
      [toX, toY],
    ];
  }
  if (toX - fromX >= 2 * STUB)
    return [
      [fromX, fromY],
      [fromX + STUB, fromY],
      [fromX + STUB, toY],
      [toX, toY],
    ];
  // the next task starts before the arrow has room to turn: back between the two lines
  const betweenY = fromY + (Math.sign(toY - fromY) * BLOCK_HEIGHT) / 2;
  return [
    [fromX, fromY],
    [fromX + STUB, fromY],
    [fromX + STUB, betweenY],
    [toX - STUB, betweenY],
    [toX - STUB, toY],
    [toX, toY],
  ];
};

/** Where an end of an arrow is taken: on the arrow, clear of the bar it is at and of the handle there. */
const getEndPoint = ([x, y]: TPoint, [nextX]: TPoint): TPoint => [x + Math.sign(nextX - x) * STUB, y];

/** The arrows that have a way through the lines that are drawn, each with the corners of its way. */
export const getDrawnArrows = (props: TArrowWaysProps) =>
  props.arrows.flatMap((arrow) => {
    const points = getPoints(arrow, props);
    return points ? [{ arrow, points }] : [];
  });

const ArrowPaths = memo(function ArrowPaths(props: TPathsProps) {
  const { schedule, selectedArrowId, causeArrowIds, isEditable, onClick, onHover, onEndPress } = props;

  return (
    <svg className="absolute top-0 left-0 h-full w-px overflow-visible">
      {/* a head per state: a marker takes its colour from where it is defined, not from the path that ends with it */}
      {Object.entries(CLASS_NAMES).map(([state, className]) => (
        <marker
          key={state}
          id={`timeline-arrow-head-${state}`}
          className={className}
          markerUnits="userSpaceOnUse"
          markerWidth={7}
          markerHeight={8}
          refX={7}
          refY={4}
          orient="auto"
        >
          <path d="M 0 0 L 7 4 L 0 8 z" fill="currentColor" />
        </marker>
      ))}
      {getDrawnArrows(props).map(({ arrow, points }) => {
        const path = getPath(points);
        const isSelected = arrow.id === selectedArrowId;
        const isConflictCause = causeArrowIds.includes(arrow.id);
        const state =
          isConflictCause || schedule.conflicts.some((conflict) => conflict.arrowId === arrow.id)
            ? "danger"
            : isSelected || schedule.criticalArrowIds.includes(arrow.id)
              ? "accent"
              : "normal";
        const ends: [TArrowEnd, TPoint][] = [
          ["tail", getEndPoint(points[0], points[1])],
          ["head", getEndPoint(points[points.length - 1], points[points.length - 2])],
        ];
        return (
          <g key={arrow.id} className={cn("group/arrow", CLASS_NAMES[state])}>
            <path
              d={path}
              fill="none"
              stroke="currentColor"
              strokeWidth={isSelected ? 3 : isConflictCause ? 2.5 : 1.5}
              markerEnd={`url(#timeline-arrow-head-${state})`}
            />
            <path
              d={path}
              fill="none"
              stroke="transparent"
              strokeWidth={12}
              className="[pointer-events:stroke] cursor-pointer"
              onClick={() => onClick(arrow)}
              onPointerEnter={() => onHover(arrow)}
              onPointerLeave={() => onHover(undefined)}
            />
            {isEditable &&
              ends.map(([end, [x, y]]) => (
                <circle
                  key={end}
                  cx={x}
                  cy={y}
                  r={4.5}
                  stroke="currentColor"
                  strokeWidth={1.5}
                  className="[pointer-events:all] cursor-grab fill-(--background-color-surface-1) opacity-0 group-hover/arrow:opacity-100"
                  onPointerDown={(e) => onEndPress(e, arrow, end)}
                  onPointerEnter={() => onHover(arrow)}
                  onPointerLeave={() => onHover(undefined)}
                />
              ))}
          </g>
        );
      })}
    </svg>
  );
});

const ArrowControls = memo(function ArrowControls(props: TControlsProps) {
  const { viewTop, viewBottom, renderControl } = props;

  return getDrawnArrows(props).map(({ arrow, points }) => {
    // on the last stretch of the arrow between the lines: in its middle, or as near to it as is in view
    const [x, fromY] = points[points.length - 3];
    const [, toY] = points[points.length - 2];
    const [headX] = points[points.length - 1];
    const top = Math.max(Math.min(fromY, toY), viewTop);
    const bottom = Math.min(Math.max(fromY, toY), viewBottom);
    return (
      <div
        key={arrow.id}
        className="pointer-events-auto absolute"
        style={{ left: x, top: clamp((fromY + toY) / 2, top, Math.max(top, bottom)) }}
      >
        {renderControl(arrow, { isRight: headX > x, isBelow: toY > fromY })}
      </div>
    );
  });
});

// The arrows, their texts and their controls are drawn for a scale and moved as a whole, so a pan draws none of
// them again.
export const getArrowLayerStyle = (view: TTimelineView) => ({ transform: `translateX(${getDayX(view, BASE_DAY)}px)` });

/** The arrows between the bars. */
export function TimelineArrows(props: Omit<TPathsProps, "pxPerDay"> & { view: TTimelineView }) {
  const { view, ...pathsProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getArrowLayerStyle(view)}>
      <ArrowPaths pxPerDay={view.pxPerDay} {...pathsProps} />
    </div>
  );
}

/** What `renderControl` gives for each of the arrows, at a place on the arrow. */
export function TimelineArrowControls(props: Omit<TControlsProps, "pxPerDay"> & { view: TTimelineView }) {
  const { view, ...controlsProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getArrowLayerStyle(view)}>
      <ArrowControls pxPerDay={view.pxPerDay} {...controlsProps} />
    </div>
  );
}

/** The arrow that is being drawn, from its handle to the pointer. */
export function TimelineDrawnArrow(props: { from: TPoint; to: TPoint; isRefused: boolean }) {
  const { from, to, isRefused } = props;

  return (
    <svg
      className={cn(
        "absolute top-0 left-0 h-full w-px overflow-visible",
        isRefused ? "text-danger-primary" : "text-accent-primary"
      )}
    >
      <path d={`M ${from} L ${to}`} fill="none" stroke="currentColor" strokeWidth={1.5} strokeDasharray="4 3" />
    </svg>
  );
}
