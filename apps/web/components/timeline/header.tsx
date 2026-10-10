/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { memo, useMemo } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { EStartOfTheWeek } from "@plane/types";
import { cn } from "@plane/utils";
// local imports
import type { TTimelineInterval, TTimelineUnit, TTimelineView } from "./scale";
import { getDayX, getIntervals, getLastDay, getPrimaryUnit, LARGER_UNIT, MS_PER_DAY } from "./scale";

type Props = {
  view: TTimelineView;
  today: number;
  startOfWeek: EStartOfTheWeek;
};

// an interval at least this wide has room for the longer label
const LONG_LABEL_WIDTH = 72;
const LARGER_LABEL_PADDING = 12;

const getFormat = (locale: string, options: Intl.DateTimeFormatOptions) => {
  const format = new Intl.DateTimeFormat(locale, { ...options, timeZone: "UTC" });
  return (day: number) => format.format(day * MS_PER_DAY);
};

/** Per unit, the label of an interval and a longer one for an interval that has the room. */
const getLabels = (locale: string) => {
  const dayOfMonth = getFormat(locale, { day: "numeric" });
  const weekday = getFormat(locale, { weekday: "short", day: "numeric" });
  const monthAndDay = getFormat(locale, { month: "short", day: "numeric" });
  const shortMonth = getFormat(locale, { month: "short" });
  const month = getFormat(locale, { month: "long" });
  const monthOfYear = getFormat(locale, { month: "long", year: "numeric" });
  const year = getFormat(locale, { year: "numeric" });
  const labels: Record<TTimelineUnit, (interval: TTimelineInterval) => [string, string?]> = {
    day: ({ start }) => [dayOfMonth(start), weekday(start)],
    week: ({ start }) => [dayOfMonth(start), monthAndDay(start)],
    month: ({ start }) => [shortMonth(start), month(start)],
    quarter: ({ index }) => [`Q${(index % 4) + 1}`],
    year: ({ start }) => [year(start)],
    decade: ({ start, end }) => [`${year(start)} – ${year(end - 1)}`],
  };
  return { ...labels, monthOfYear };
};

/**
 * The two lines above the timeline: the unit it is divided by at the present scale, and the larger unit above it.
 * They change with the view only, not with the plan that a drag previews.
 */
export const TimelineHeader = memo(function TimelineHeader(props: Props) {
  const { view, today, startOfWeek } = props;
  // translation
  const { currentLocale } = useTranslation();
  // derived values
  const labels = useMemo(() => getLabels(currentLocale), [currentLocale]);
  const unit = getPrimaryUnit(view.pxPerDay);
  const largerUnit = LARGER_UNIT[unit];

  return (
    <>
      {getIntervals(largerUnit, view.originDay, getLastDay(view), startOfWeek).map((interval) => {
        const left = getDayX(view, interval.start);
        return (
          <div
            key={interval.start}
            className="absolute top-0 flex h-7 items-center overflow-hidden border-l border-subtle-1 text-13 whitespace-nowrap text-secondary"
            style={{
              left,
              width: getDayX(view, interval.end) - left,
              // the label stays in view while a part of its interval is
              paddingLeft: Math.max(-left, 0) + LARGER_LABEL_PADDING,
            }}
          >
            {largerUnit === "month" ? labels.monthOfYear(interval.start) : labels[largerUnit](interval)[0]}
          </div>
        );
      })}
      {getIntervals(unit, view.originDay, getLastDay(view), startOfWeek).map((interval) => {
        const left = getDayX(view, interval.start);
        const width = getDayX(view, interval.end) - left;
        const [label, longLabel = label] = labels[unit](interval);
        return (
          <div
            key={interval.start}
            className="absolute top-7 flex h-5 items-center justify-center overflow-hidden border-l border-subtle-1 text-11 font-medium whitespace-nowrap text-tertiary"
            style={{ left, width }}
          >
            <span
              className={cn("rounded-sm px-1", {
                "bg-accent-primary text-on-color": unit === "day" && interval.start === today,
              })}
            >
              {width >= LONG_LABEL_WIDTH ? longLabel : label}
            </span>
          </div>
        );
      })}
    </>
  );
});
