/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { clamp } from "lodash-es";
// plane imports
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import { BAR_HEIGHT, BAR_TOP, MARKER_CLASS_NAME } from "./bar";
import type { TTimelineView } from "./scale";
import { getDayX, MIN_BAR_WIDTH } from "./scale";

type Props = {
  view: TTimelineView;
  // the first and the last day of the task
  start: number;
  end: number;
  lineIndex: number;
  // it stands under the bar: above the first line in view the header of the timeline is in the way
  isBelow: boolean;
};

// how far the dimension line is from its bar, and the number from the line when it does not stand on it
const LINE_DISTANCE = 13;
const NUMBER_DISTANCE = 6;
const HEAD_LENGTH = 7;
const HEAD_WIDTH = 8;
// what the number takes, for telling whether it has room between the arrowheads
const CHARACTER_WIDTH = 6;
const NUMBER_PADDING = 16;

/**
 * The dimension line of a bar whose edge is held: as wide as the bar, with the days the task lasts in its middle.
 * The dates beside the bar say where its edges are; this says what a resize is made for, how long the task is.
 */
export function TimelineBarDimension(props: Props) {
  const { view, start, end, lineIndex, isBelow } = props;
  // translation
  const { t } = useTranslation();
  // derived values
  const left = getDayX(view, start);
  const width = Math.max(getDayX(view, end + 1) - left, MIN_BAR_WIDTH);
  const barTop = lineIndex * BLOCK_HEIGHT + BAR_TOP;
  const top = isBelow ? barTop + BAR_HEIGHT + LINE_DISTANCE : barTop - LINE_DISTANCE;
  const number = t("timeline.duration", { days: end - start + 1 });
  const numberWidth = number.length * CHARACTER_WIDTH + NUMBER_PADDING;
  // between the arrowheads when there is room for it, else beyond the line, away from the bar
  const isNumberOnLine = width >= numberWidth + 2 * (HEAD_LENGTH + NUMBER_DISTANCE);
  // A bar too narrow for two arrowheads has them outside, pointing at its edges.
  const headLength = width < 3 * HEAD_LENGTH ? -HEAD_LENGTH : HEAD_LENGTH;
  const tail = headLength < 0 ? HEAD_LENGTH + NUMBER_DISTANCE : 0;
  // the number stays in the part of the line that is in view, and is not cut at an edge of the timeline
  const numberX = clamp(
    (Math.max(left, 0) + Math.min(left + width, view.width)) / 2,
    numberWidth / 2,
    view.width - numberWidth / 2
  );

  return (
    <>
      <svg className="absolute h-px overflow-visible text-accent-primary" style={{ left, top, width }}>
        <path d={`M ${-tail} 0 H ${width + tail}`} stroke="currentColor" />
        <path d={`M ${headLength} ${-HEAD_WIDTH / 2} L 0 0 L ${headLength} ${HEAD_WIDTH / 2} z`} fill="currentColor" />
        <path
          d={`M ${width - headLength} ${-HEAD_WIDTH / 2} L ${width} 0 L ${width - headLength} ${HEAD_WIDTH / 2} z`}
          fill="currentColor"
        />
      </svg>
      <div
        className={cn(MARKER_CLASS_NAME, "absolute -translate-x-1/2", {
          "-translate-y-1/2": isNumberOnLine,
          "-translate-y-full": !isNumberOnLine && !isBelow,
        })}
        style={{
          left: numberX,
          top: isNumberOnLine ? top : top + (isBelow ? 1 : -1) * (HEAD_WIDTH / 2 + NUMBER_DISTANCE / 2),
        }}
      >
        {number}
      </div>
    </>
  );
}
