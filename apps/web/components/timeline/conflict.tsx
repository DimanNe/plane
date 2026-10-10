/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { Popover, PopoverContent } from "@makeplane/propel/components/popover";
import { applyWayOut } from "@plane/blocks/timeline-schedule";
import type { TConflict, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import { renderFormattedDate } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// local imports
import type { TTimelineOperation } from "./operation";
import { runOperation } from "./operation";

type Props = {
  conflict: TConflict;
  arrow: TScheduleArrow;
  operation: TTimelineOperation;
  // the ways out are offered; else the explanation only tells
  isEditable: boolean;
  // the line of the fixed task is under the arrow's place, not above it
  isNextBelow: boolean;
  onClose: () => void;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
};

const formatDay = (day: string) => renderFormattedDate(day, "MMM d");

/**
 * Why an arrow is a conflict, at the arrow while the pointer is over it: a sentence made of the conflict the
 * schedule reports, and the ways out of it, each applied by a click as one operation.
 */
export const TimelineConflict = observer(function TimelineConflict(props: Props) {
  const { conflict, arrow, operation, isEditable, isNextBelow, onClose, onPointerEnter, onPointerLeave } = props;
  // states
  const [anchor, setAnchor] = useState<HTMLSpanElement | null>(null);
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // translation
  const { t } = useTranslation();

  return (
    <>
      <span ref={setAnchor} />
      {anchor && (
        <Popover open onOpenChange={onClose}>
          <PopoverContent
            anchor={anchor}
            // away from the fixed task, and to the right of the arrow: what produces the conflict is to its left
            side={isNextBelow ? "top" : "bottom"}
            align="start"
            sideOffset={12}
            initialFocus={false}
            onPointerEnter={onPointerEnter}
            // it stays while its text is being selected, also when the pointer goes over its edge
            onPointerLeave={(e) => e.buttons === 0 && onPointerLeave()}
          >
            <div className="flex max-w-96 flex-col gap-2 select-text">
              <p className="text-body-xs-regular text-primary">
                {t("timeline.conflict.fixed", {
                  task: getIssueById(conflict.taskId)?.name,
                  day: formatDay(conflict.fixedDay),
                })}{" "}
                {t(`timeline.conflict.asks.${arrow.kind}`, {
                  day: formatDay(conflict.askedDay),
                  days: arrow.delay,
                  previous: getIssueById(arrow.previousId)?.name,
                  anchor: formatDay(conflict.anchorDay),
                })}
              </p>
              {isEditable && (
                <div className="flex flex-wrap gap-1.5">
                  {conflict.waysOut.map((wayOut) => (
                    <Button
                      key={wayOut.way}
                      variant="secondary"
                      size="sm"
                      stretch="auto"
                      label={t(`timeline.conflict.ways_out.${wayOut.way}`, {
                        day: "day" in wayOut ? formatDay(wayOut.day) : undefined,
                        days: "delay" in wayOut ? wayOut.delay : undefined,
                      })}
                      onClick={() => {
                        runOperation(operation, (plan) => applyWayOut(plan, conflict, wayOut));
                        onClose();
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </>
  );
});
