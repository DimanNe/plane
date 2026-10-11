/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { memo } from "react";
import { clamp, groupBy, sortBy } from "lodash-es";
// plane imports
import type { TSchedule, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { cn } from "@plane/utils";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import { BAR_HEIGHT } from "./bar";
import { ARROW_LINE_LOOKS, getArrowState, getShownArrowState } from "./arrow-state";
import type { TArrowStates } from "./arrow-state";
import type { TTimelineView } from "./scale";
import { BASE_DAY, getDayDistance, getDayX, MIN_BAR_WIDTH } from "./scale";

export type TPoint = [x: number, y: number];

/** An end of an arrow: its tail is at the previous task, its head at the next one. */
export type TArrowEnd = "tail" | "head";

/** An arrow that is drawn: the corners of its way, and the width of the strip along it that takes the pointer. */
export type TDrawnArrow = { arrow: TScheduleArrow; points: TPoint[]; hitWidth: number };

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

type TPathsProps = {
  drawnArrows: TDrawnArrow[];
  schedule: TSchedule;
  arrowStates: TArrowStates;
  // the arrows that produce the conflict the pointer is over
  causeArrowIds: string[];
  isEditable: boolean;
  onClick: (arrow: TScheduleArrow, click: React.MouseEvent) => void;
  onHover: (arrow: TScheduleArrow | undefined) => void;
  onEndPress: (press: React.PointerEvent, arrow: TScheduleArrow, end: TArrowEnd) => void;
};

// how far an arrow runs out of a bar and into one before it turns: past the handle at that end of the bar
export const STUB = 22;
// Of the arrows at one edge of a bar each turns this much farther from the bar than the one before it, so that
// they run beside each other.
const STUB_STEP = 8;
// how round a turn of an arrow is where its stretches are long enough
const CORNER_RADIUS = 14;
// An arrow leaves a bar straight for this long, and comes into one straight for the length of its head.
const TAIL_LENGTH = 4;
const HEAD_LENGTH = 8;
// the widest and the narrowest strip along an arrow that takes the pointer
const HIT_WIDTH = 12;
const MIN_HIT_WIDTH = 6;
// The colour of an arrow: of a conflict and of what produces it, of a critical or a selected arrow, of the others;
// and of an arrow whose days count in the move that is going on, and of one that stops that move.
const CLASS_NAMES = {
  normal: "text-placeholder",
  accent: "text-accent-primary",
  danger: "text-danger-primary",
  changing: "text-success-primary",
  stopping: "text-warning-primary",
};
// The head of an arrow, and the head of one that stops a move: with a bar across its tip, at the edge of the bar
// that goes no further.
const HEAD_PATH = "M 0 0 L 7 4 L 0 8 z";
const STOPPING_HEAD_PATH = `${HEAD_PATH} M 5.5 -3 h 2.5 v 14 h -2.5 z`;

// Where an arrow ends on the edge of a bar: how far under the middle of the bar, how far the next end on that edge
// is, and how many of the other arrows of the edge turn nearer to the bar.
type TEndPlace = { offset: number; spacing: number; turnsBefore: number };

/**
 * The ends of the arrows at each edge of each bar, heads and tails alike, spread evenly over the height of the
 * bar, so that each arrow can be pointed at by itself right up to the bar. An arrow whose other task is on a
 * higher line ends higher and, going up, turns nearer to the bar; so the arrows of one edge do not cross. Only
 * the lines decide the order: it stays as it is while a bar is dragged sideways.
 */
const getEndPlaces = ({ arrows, days, lineIndexes }: TArrowWaysProps) => {
  const ends = arrows.flatMap((arrow) => {
    const previousLine = lineIndexes.get(arrow.previousId);
    const nextLine = lineIndexes.get(arrow.nextId);
    if (previousLine === undefined || nextLine === undefined || !days[arrow.previousId] || !days[arrow.nextId])
      return [];
    const [tailEdge, headEdge] = arrow.kind.split("-");
    return [
      { arrow, end: "tail" as const, edge: `${arrow.previousId} ${tailEdge}`, line: previousLine, otherLine: nextLine },
      { arrow, end: "head" as const, edge: `${arrow.nextId} ${headEdge}`, line: nextLine, otherLine: previousLine },
    ];
  });
  const places: Record<string, Record<TArrowEnd, TEndPlace>> = {};
  for (const endsOfEdge of Object.values(groupBy(ends, "edge"))) {
    const spacing = BAR_HEIGHT / (endsOfEdge.length + 1);
    sortBy(endsOfEdge, "otherLine").forEach(({ arrow, end, line, otherLine }, index) => {
      places[arrow.id] = {
        ...places[arrow.id],
        [end]: {
          offset: (index + 1) * spacing - BAR_HEIGHT / 2,
          spacing: endsOfEdge.length > 1 ? spacing : Infinity,
          // of the arrows that go up the highest turns first, of those that go down the lowest
          turnsBefore: otherLine < line ? index : endsOfEdge.length - 1 - index,
        },
      };
    });
  }
  return places;
};

const getDistance = ([x, y]: TPoint, [toX, toY]: TPoint) => Math.abs(toX - x) + Math.abs(toY - y);

/** The point on the way from a point straight to another, a distance from the first. */
const getPointTowards = (from: TPoint, to: TPoint, distance: number): TPoint => {
  const length = getDistance(from, to) || 1;
  return [from[0] + ((to[0] - from[0]) * distance) / length, from[1] + ((to[1] - from[1]) * distance) / length];
};

/**
 * How round each turn of a way through the points is: as round as the two stretches it joins leave room for. A
 * stretch between two turns gives each of them half of its length; the stretch at a bar gives its turn all of
 * its length but the piece that stays straight at the bar.
 */
const getRadii = (points: TPoint[]) => {
  const lastStretch = points.length - 2;
  const getRoom = (stretch: number) => {
    const length = getDistance(points[stretch], points[stretch + 1]);
    return stretch === 0 ? length - TAIL_LENGTH : stretch === lastStretch ? length - HEAD_LENGTH : length / 2;
  };
  return points
    .slice(1, -1)
    .map((_, index) => Math.max(0, Math.min(CORNER_RADIUS, getRoom(index), getRoom(index + 1))));
};

/** A line through the points with its turns rounded. */
const getPath = (points: TPoint[]) => {
  const radii = getRadii(points);
  const turns = radii.map((radius, index) => {
    const corner = points[index + 1];
    return `L ${getPointTowards(corner, points[index], radius)} Q ${corner} ${getPointTowards(corner, points[index + 2], radius)}`;
  });
  return `M ${points[0]} ${turns.join(" ")} L ${points[points.length - 1]}`;
};

/**
 * Where an end of an arrow is taken: on the arrow, past the handle of the bar it is at. That is on the stretch
 * at the bar where it is straight that far, else in the middle of the turn there.
 */
const getEndPoint = (points: TPoint[], end: TArrowEnd): TPoint => {
  const radii = getRadii(points);
  const [edge, corner, beyond, radius] =
    end === "tail"
      ? [points[0], points[1], points[2], radii[0]]
      : [points[points.length - 1], points[points.length - 2], points[points.length - 3], radii[radii.length - 1]];
  if (getDistance(edge, corner) - radius >= STUB) return getPointTowards(edge, corner, STUB);
  const [fromX, fromY] = getPointTowards(corner, edge, radius);
  const [toX, toY] = getPointTowards(corner, beyond, radius);
  return [fromX / 4 + corner[0] / 2 + toX / 4, fromY / 4 + corner[1] / 2 + toY / 4];
};

/**
 * The way of an arrow from the bar of the previous task to the bar of the next one: out of the end or the start
 * it constrains by, along the lines, into the start or the end it constrains.
 */
const getPoints = (
  arrow: TScheduleArrow,
  props: TArrowWaysProps,
  ends: Record<TArrowEnd, TEndPlace>
): TPoint[] | undefined => {
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
  const fromY = (previousLine + 0.5) * BLOCK_HEIGHT + ends.tail.offset;
  const toY = (nextLine + 0.5) * BLOCK_HEIGHT + ends.head.offset;
  const tailStub = STUB + ends.tail.turnsBefore * STUB_STEP;
  const headStub = STUB + ends.head.turnsBefore * STUB_STEP;

  if (arrow.kind !== "end-start") {
    // around the starts on their left, around the ends on their right
    const turnX =
      arrow.kind === "start-start"
        ? Math.min(fromX - tailStub, toX - headStub)
        : Math.max(fromX + tailStub, toX + headStub);
    return [
      [fromX, fromY],
      [turnX, fromY],
      [turnX, toY],
      [toX, toY],
    ];
  }
  if (toX - fromX >= tailStub + STUB)
    return [
      [fromX, fromY],
      [fromX + tailStub, fromY],
      [fromX + tailStub, toY],
      [toX, toY],
    ];
  // the next task starts before the arrow has room to turn: back between the two lines
  const betweenY = (previousLine + 0.5 + Math.sign(nextLine - previousLine) / 2) * BLOCK_HEIGHT;
  return [
    [fromX, fromY],
    [fromX + tailStub, fromY],
    [fromX + tailStub, betweenY],
    [toX - headStub, betweenY],
    [toX - headStub, toY],
    [toX, toY],
  ];
};

/**
 * The arrows that have a way through the lines that are drawn, each with the corners of its way and with the
 * width of the strip along it that takes the pointer: narrower where its ends are close to those of other arrows.
 * Found once for all that is drawn of the arrows: their lines and their texts.
 */
export const getDrawnArrows = (props: TArrowWaysProps): TDrawnArrow[] => {
  const endPlaces = getEndPlaces(props);
  return props.arrows.flatMap((arrow) => {
    const ends = endPlaces[arrow.id];
    const points = ends && getPoints(arrow, props, ends);
    const hitWidth = ends && clamp(Math.min(ends.tail.spacing, ends.head.spacing), MIN_HIT_WIDTH, HIT_WIDTH);
    return points ? [{ arrow, points, hitWidth }] : [];
  });
};

const ArrowPaths = memo(function ArrowPaths(props: TPathsProps) {
  const { drawnArrows, schedule, arrowStates, causeArrowIds, isEditable, onClick, onHover, onEndPress } = props;

  return (
    <svg className="absolute top-0 left-0 h-full w-px overflow-visible">
      {/* a head per colour: a marker takes its colour from where it is defined, not from the path that ends with it */}
      {Object.entries(CLASS_NAMES).map(([colour, className]) => (
        <marker
          key={colour}
          id={`timeline-arrow-head-${colour}`}
          className={cn("overflow-visible", className)}
          markerUnits="userSpaceOnUse"
          markerWidth={7}
          markerHeight={8}
          refX={7}
          refY={4}
          orient="auto"
        >
          <path d={colour === "stopping" ? STOPPING_HEAD_PATH : HEAD_PATH} fill="currentColor" />
        </marker>
      ))}
      {drawnArrows.map(({ arrow, points, hitWidth }) => {
        const path = getPath(points);
        const isConflictCause = causeArrowIds.includes(arrow.id);
        const state = getArrowState(arrow.id, arrowStates);
        const isInConflict =
          isConflictCause ||
          [...schedule.conflicts, ...schedule.apartLinks].some(({ arrowId }) => arrowId === arrow.id);
        const look = ARROW_LINE_LOOKS[getShownArrowState(state, isInConflict)];
        const isAccent = state === "selected" || schedule.criticalArrowIds.includes(arrow.id);
        // a move of a task has its say on an arrow before what the plan says of it
        const colour = look.colour ?? (isInConflict ? "danger" : isAccent ? "accent" : "normal");
        const ends = (["tail", "head"] as const).map((end) => [end, getEndPoint(points, end)] as const);
        return (
          <g key={arrow.id} className={cn("group/arrow", CLASS_NAMES[colour])} data-state={state}>
            <path
              d={path}
              fill="none"
              stroke="currentColor"
              strokeWidth={Math.max(look.strokeWidth, isConflictCause ? 2.5 : 0)}
              markerEnd={`url(#timeline-arrow-head-${colour})`}
            />
            <path
              d={path}
              fill="none"
              stroke="transparent"
              strokeWidth={hitWidth}
              className="[pointer-events:stroke] cursor-pointer"
              onClick={(e) => onClick(arrow, e)}
              onPointerEnter={() => onHover(arrow)}
              onPointerLeave={() => onHover(undefined)}
            />
            {isEditable &&
              ends.map(([end, [x, y]]) => (
                // An end is taken by the small circle on the arrow near its bar. It is there for the pointer while
                // the pointer is on its arrow: the circles of the other arrows at that edge are not in the way.
                <circle
                  key={end}
                  cx={x}
                  cy={y}
                  r={4.5}
                  stroke="currentColor"
                  strokeWidth={1.5}
                  className="pointer-events-none cursor-grab fill-(--background-color-surface-1) opacity-0 group-hover/arrow:pointer-events-auto group-hover/arrow:opacity-100"
                  onPointerDown={(e) => onEndPress(e, arrow, end)}
                  onClick={(e) => onClick(arrow, e)}
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

// The arrows and their texts are drawn for a scale and moved as a whole, so a pan draws none of them again.
export const getArrowLayerStyle = (view: TTimelineView) => ({ transform: `translateX(${getDayX(view, BASE_DAY)}px)` });

/** The arrows between the bars. */
export function TimelineArrows(props: TPathsProps & { view: TTimelineView }) {
  const { view, ...pathsProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getArrowLayerStyle(view)}>
      <ArrowPaths {...pathsProps} />
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
