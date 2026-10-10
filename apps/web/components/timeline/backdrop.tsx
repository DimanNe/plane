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
import {
  BASE_DAY,
  getDayX,
  getIntervals,
  getLastDay,
  getPrimaryUnit,
  LARGER_UNIT,
  WEEKEND_MIN_PX_PER_DAY,
} from "./scale";

type Props = {
  view: TTimelineView;
  startOfWeek: EStartOfTheWeek;
};

/**
 * What lies behind the lines of the timeline: every other interval of the unit it is divided by in light grey,
 * the weekends shaded while days are wide enough to tell apart, and a line where an interval of the larger unit starts.
 * It changes with the view only, not with the plan that a drag previews.
 */
export const TimelineBackdrop = memo(function TimelineBackdrop(props: Props) {
  const { view, startOfWeek } = props;
  // derived values
  const unit = getPrimaryUnit(view.pxPerDay);
  const lastDay = getLastDay(view);
  const getPlace = (start: number, end: number) => ({ left: start - BASE_DAY, width: end - start });

  return (
    <>
      {/* a pixel a day, stretched to the scale as one layer: a change of the view moves this element and no other */}
      <div
        className="absolute inset-y-0 left-0 origin-left"
        style={{ transform: `translateX(${getDayX(view, BASE_DAY)}px) scaleX(${view.pxPerDay})` }}
      >
        {getIntervals(unit, view.originDay, lastDay, startOfWeek).map(
          ({ start, end, index }) =>
            index % 2 !== 0 && (
              <div key={start} className="absolute inset-y-0 bg-layer-1-hover" style={getPlace(start, end)} />
            )
        )}
        {view.pxPerDay >= WEEKEND_MIN_PX_PER_DAY &&
          // a week that starts on Saturday starts with the weekend
          getIntervals("week", view.originDay, lastDay, EStartOfTheWeek.SATURDAY).map(({ start }) => (
            <div key={-start} className="absolute inset-y-0 bg-layer-1-active" style={getPlace(start, start + 2)} />
          ))}
      </div>
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
