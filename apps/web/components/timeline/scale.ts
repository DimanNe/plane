/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createContext } from "react";
import type { EStartOfTheWeek } from "@plane/types";

// The timeline has one scale: pixels per day. A day is a whole number of days since 1970-01-01, so a
// calendar date is the same day in every time zone and no day is longer or shorter than another.

export type TTimelineView = {
  /** The day at the left edge of the timeline; a fraction when the edge is inside a day. */
  originDay: number;
  pxPerDay: number;
  /** The width of the timeline in pixels. */
  width: number;
};

/** The view of the timeline a component is drawn in: for a bar, which a change of the view draws without its line. */
export const TimelineViewContext = createContext<TTimelineView>({ originDay: 0, pxPerDay: 1, width: 0 });

/** A unit the timeline can be divided by. */
export type TPrimaryUnit = "day" | "week" | "month" | "quarter" | "year";

export type TTimelineUnit = TPrimaryUnit | "decade";

export type TTimelineInterval = {
  start: number;
  /** The first day after the interval. */
  end: number;
  /** Counts the intervals of the unit, so that every other one can be told from its neighbours. */
  index: number;
};

export const MS_PER_DAY = 24 * 60 * 60 * 1000;

// a year in 36 pixels, a day in 160
export const MIN_PX_PER_DAY = 0.1;
export const MAX_PX_PER_DAY = 160;
/** The least width of an interval of the unit the timeline is divided by. */
const MIN_INTERVAL_WIDTH = 32;
/** Weekends are told apart from this scale on. */
export const WEEKEND_MIN_PX_PER_DAY = 5;
/** A task shorter than this at the present scale is still drawn this wide. */
export const MIN_BAR_WIDTH = 6;

// the units shorter than a year, with their least number of days
const UNIT_DAYS: [TPrimaryUnit, number][] = [
  ["day", 1],
  ["week", 7],
  ["month", 28],
  ["quarter", 90],
];
const UNIT_MONTHS = { month: 1, quarter: 3, year: 12, decade: 120 };

export const LARGER_UNIT: Record<TPrimaryUnit, TTimelineUnit> = {
  day: "month",
  week: "month",
  month: "year",
  quarter: "year",
  year: "decade",
};

export const getDayOfDate = (date: string) => Date.parse(date) / MS_PER_DAY;

export const getDateOfDay = (day: number) => new Date(day * MS_PER_DAY).toISOString().slice(0, 10);

/** A moment on the scale of days, by the clock of the user. */
export const getDayOfTime = (time: Date) =>
  Date.UTC(time.getFullYear(), time.getMonth(), time.getDate(), time.getHours(), time.getMinutes()) / MS_PER_DAY;

/** The smallest unit whose intervals have room for their label. */
export const getPrimaryUnit = (pxPerDay: number): TPrimaryUnit =>
  UNIT_DAYS.find(([, days]) => days * pxPerDay >= MIN_INTERVAL_WIDTH)?.[0] ?? "year";

const getInterval = (unit: TTimelineUnit, day: number, startOfWeek: EStartOfTheWeek): TTimelineInterval => {
  if (unit === "day") return { start: day, end: day + 1, index: day };
  if (unit === "week") {
    // 1970-01-01 was a Thursday
    const start = day - ((((day + 4 - startOfWeek) % 7) + 7) % 7);
    return { start, end: start + 7, index: Math.floor(start / 7) };
  }
  const months = UNIT_MONTHS[unit];
  const date = new Date(day * MS_PER_DAY);
  const index = Math.floor((date.getUTCFullYear() * 12 + date.getUTCMonth()) / months);
  const getMonthStart = (month: number) => Date.UTC(Math.floor(month / 12), month % 12, 1) / MS_PER_DAY;
  return { start: getMonthStart(index * months), end: getMonthStart((index + 1) * months), index };
};

/** The intervals of a unit that have a day in `from` to `to`. */
export const getIntervals = (
  unit: TTimelineUnit,
  from: number,
  to: number,
  startOfWeek: EStartOfTheWeek
): TTimelineInterval[] => {
  const intervals: TTimelineInterval[] = [];
  for (let day = Math.floor(from); day < to; day = intervals[intervals.length - 1].end)
    intervals.push(getInterval(unit, day, startOfWeek));
  return intervals;
};

/**
 * A day near the present. What is drawn once and then moved as a whole on a change of the view is placed from
 * it, which keeps the distances small enough to be drawn exactly.
 */
export const BASE_DAY = Math.floor(Date.now() / MS_PER_DAY);

/** The distance of the start of a day from the start of `BASE_DAY`, in whole pixels. */
export const getDayDistance = (pxPerDay: number, day: number) => Math.round((day - BASE_DAY) * pxPerDay);

/**
 * The distance of the start of a day from the left edge of the timeline. Everything that starts or ends with a
 * day is placed by it, so bars, arrows and the header meet on the same pixel.
 */
export const getDayX = (view: TTimelineView, day: number) =>
  getDayDistance(view.pxPerDay, day) - getDayDistance(view.pxPerDay, view.originDay);

/** The day at the right edge of the timeline. */
export const getLastDay = (view: TTimelineView) => view.originDay + view.width / view.pxPerDay;
