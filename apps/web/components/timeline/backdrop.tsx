/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { memo } from "react";
// plane imports
import { EStartOfTheWeek } from "@plane/types";
// local imports
import type { TTimelineView } from "./scale";
import { BASE_DAY, getDayX, getIntervals, getLastDay, getPrimaryUnit, LARGER_UNIT } from "./scale";

type Props = {
  view: TTimelineView;
  startOfWeek: EStartOfTheWeek;
};

/**
 * What lies behind the lines of the timeline: grey bands, and lines where intervals begin. There are two tones and
 * no more, so that every change of the ground means one thing at a scale:
 * - days: the weekends are grey, and a thin line parts the days;
 * - weeks: every other month is grey, as the upper line of the header reads, and a thin line parts the weeks;
 * - months, quarters, years: every other one is grey.
 * At every scale a line stands where an interval of the header's upper line begins.
 * It changes with the view only, not with the plan that a drag previews.
 */
export const TimelineBackdrop = memo(function TimelineBackdrop(props: Props) {
  const { view, startOfWeek } = props;
  // derived values
  const unit = getPrimaryUnit(view.pxPerDay);
  const lastDay = getLastDay(view);
  const bands =
    unit === "day"
      ? // a week that starts on Saturday starts with the weekend
        getIntervals("week", view.originDay, lastDay, EStartOfTheWeek.SATURDAY).map(({ start }) => ({
          start,
          end: start + 2,
        }))
      : getIntervals(unit === "week" ? "month" : unit, view.originDay, lastDay, startOfWeek).filter(
          ({ index }) => index % 2 !== 0
        );
  const thinLineDays =
    unit === "day" || unit === "week"
      ? getIntervals(unit, view.originDay, lastDay, startOfWeek).map(({ start }) => start)
      : [];

  return (
    <>
      {/* a pixel a day, stretched to the scale as one layer: a change of the view moves this element and no other */}
      <div
        className="absolute inset-y-0 left-0 origin-left"
        style={{ transform: `translateX(${getDayX(view, BASE_DAY)}px) scaleX(${view.pxPerDay})` }}
      >
        {bands.map(({ start, end }) => (
          <div
            key={start}
            className="absolute inset-y-0 bg-layer-1-hover"
            style={{ left: start - BASE_DAY, width: end - start }}
          />
        ))}
      </div>
      {thinLineDays.map((day) => (
        <div key={-day} className="absolute inset-y-0 border-l border-subtle" style={{ left: getDayX(view, day) }} />
      ))}
      {getIntervals(LARGER_UNIT[unit], view.originDay, lastDay, startOfWeek).map(({ start }) => (
        <div
          key={start}
          className="absolute inset-y-0 border-l border-subtle-1"
          style={{ left: getDayX(view, start) }}
        />
      ))}
    </>
  );
});
