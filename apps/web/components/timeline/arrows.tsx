/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { memo } from "react";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import type { TTimelineView } from "./scale";
import { BASE_DAY, getDayDistance, getDayX, MIN_BAR_WIDTH } from "./scale";
import type { TSchedule, TScheduleArrow } from "./types";

type TPoint = [x: number, y: number];

// what the way of an arrow depends on
type TWaysProps = {
  arrows: TScheduleArrow[];
  // the first and the last day of every task that has a bar
  days: Record<string, { start: number; end: number }>;
  lineIndexes: Map<string, number>;
  // the lines that are drawn
  firstLine: number;
  lastLine: number;
  pxPerDay: number;
};

type TPathsProps = TWaysProps & { schedule: TSchedule; onClick: (arrow: TScheduleArrow) => void };

type TControlsProps = TWaysProps & { renderControl: (arrow: TScheduleArrow) => ReactNode };

// how far an arrow runs straight out of a bar and into one
const STUB = 12;
const CORNER_RADIUS = 5;
// the colour of an arrow by its state
const CLASS_NAMES = {
  normal: "text-placeholder",
  critical: "text-accent-primary",
  conflict: "text-danger-primary",
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
const getPoints = (arrow: TScheduleArrow, props: TWaysProps): TPoint[] | undefined => {
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

const getDrawnArrows = (props: TWaysProps) =>
  props.arrows.flatMap((arrow) => {
    const points = getPoints(arrow, props);
    return points ? [{ arrow, points }] : [];
  });

const ArrowPaths = memo(function ArrowPaths(props: TPathsProps) {
  const { schedule, onClick } = props;

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
        const state = schedule.conflicts.some((conflict) => conflict.arrowId === arrow.id)
          ? "conflict"
          : schedule.criticalArrowIds.includes(arrow.id)
            ? "critical"
            : "normal";
        return (
          <g key={arrow.id} className={CLASS_NAMES[state]}>
            <path
              d={path}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              markerEnd={`url(#timeline-arrow-head-${state})`}
            />
            <path
              d={path}
              fill="none"
              stroke="transparent"
              strokeWidth={12}
              className="[pointer-events:stroke] cursor-pointer"
              onClick={() => onClick(arrow)}
            />
          </g>
        );
      })}
    </svg>
  );
});

const ArrowControls = memo(function ArrowControls(props: TControlsProps) {
  return getDrawnArrows(props).map(({ arrow, points }) => {
    // on the last stretch of the arrow between the lines
    const [x, fromY] = points[points.length - 3];
    const [, toY] = points[points.length - 2];
    return (
      <div
        key={arrow.id}
        className="pointer-events-auto absolute w-max -translate-x-1/2 -translate-y-1/2"
        style={{ left: x, top: (fromY + toY) / 2 }}
      >
        {props.renderControl(arrow)}
      </div>
    );
  });
});

// The arrows and their controls are drawn for a scale and moved as a whole, so a pan draws none of them again.
const getLayerStyle = (view: TTimelineView) => ({ transform: `translateX(${getDayX(view, BASE_DAY)}px)` });

/** The arrows between the bars. */
export function TimelineArrows(props: Omit<TPathsProps, "pxPerDay"> & { view: TTimelineView }) {
  const { view, ...pathsProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getLayerStyle(view)}>
      <ArrowPaths pxPerDay={view.pxPerDay} {...pathsProps} />
    </div>
  );
}

/** What `renderControl` gives for each arrow, on the arrow. */
export function TimelineArrowControls(props: Omit<TControlsProps, "pxPerDay"> & { view: TTimelineView }) {
  const { view, ...controlsProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getLayerStyle(view)}>
      <ArrowControls pxPerDay={view.pxPerDay} {...controlsProps} />
    </div>
  );
}
