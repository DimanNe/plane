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
import { applyWayOut, getDelayDays, removeArrow, setArrowMode } from "@plane/blocks/timeline-schedule";
import type { TApartLink, TConflict, TPlan, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import { renderFormattedDate } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// local imports
import type { TTimelineOperation } from "./operation";
import { runOperation } from "./operation";

type TCardProps = {
  operation: TTimelineOperation;
  // the ways out are offered; else the explanation only tells
  isEditable: boolean;
  // the line of the next task is under the arrow's place, not above it
  isNextBelow: boolean;
  onClose: () => void;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
};

type TWayOutButton = { key: string; label: string; change: (plan: TPlan) => TPlan };

const formatDay = (day: string) => renderFormattedDate(day, "MMM d");

/**
 * Why the plan does not keep an arrow, at the arrow while the pointer is over it: a sentence, and the ways out,
 * each applied by a click as one operation.
 */
function ConflictCard(props: TCardProps & { sentence: string; waysOut: TWayOutButton[] }) {
  const { sentence, waysOut, operation, isEditable, isNextBelow, onClose, onPointerEnter, onPointerLeave } = props;
  // states
  const [anchor, setAnchor] = useState<HTMLSpanElement | null>(null);

  return (
    <>
      <span ref={setAnchor} />
      {anchor && (
        <Popover open onOpenChange={onClose}>
          <PopoverContent
            anchor={anchor}
            // away from the next task, and to the right of the arrow: what produces the conflict is to its left
            side={isNextBelow ? "top" : "bottom"}
            align="start"
            sideOffset={12}
            initialFocus={false}
            onPointerEnter={onPointerEnter}
            // it stays while its text is being selected, also when the pointer goes over its edge
            onPointerLeave={(e) => e.buttons === 0 && onPointerLeave()}
          >
            <div className="flex max-w-96 flex-col gap-2 select-text">
              <p className="text-body-xs-regular text-primary">{sentence}</p>
              {isEditable && (
                <div className="flex flex-wrap gap-1.5">
                  {waysOut.map(({ key, label, change }) => (
                    <Button
                      key={key}
                      variant="secondary"
                      size="sm"
                      stretch="auto"
                      label={label}
                      onClick={() => {
                        runOperation(operation, change);
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
}

/** A conflict as the schedule reports it: a task fixed on a day before the day its arrow asks for. */
export const TimelineConflict = observer(function TimelineConflict(
  props: TCardProps & { conflict: TConflict; arrow: TScheduleArrow }
) {
  const { conflict, arrow, ...cardProps } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // translation
  const { t } = useTranslation();

  return (
    <ConflictCard
      sentence={`${t("timeline.conflict.fixed", {
        task: getIssueById(conflict.taskId)?.name,
        day: formatDay(conflict.fixedDay),
      })} ${t(`timeline.conflict.asks.${arrow.kind}`, {
        day: formatDay(conflict.askedDay),
        days: getDelayDays(arrow.delay),
        previous: getIssueById(arrow.previousId)?.name,
        anchor: formatDay(conflict.anchorDay),
      })}`}
      waysOut={conflict.waysOut.map((wayOut) => ({
        key: wayOut.way,
        label: t(`timeline.conflict.ways_out.${wayOut.way}`, {
          day: "day" in wayOut ? formatDay(wayOut.day) : undefined,
          days: "delay" in wayOut ? wayOut.delay : undefined,
        }),
        change: (plan) => applyWayOut(plan, conflict, wayOut),
      }))}
      {...cardProps}
    />
  );
});

/**
 * A link that is apart: the arrow says that its two tasks move as one, and another arrow holds its next task
 * later. The ways out make the arrow say what is there, or take it away.
 */
export const TimelineApartLink = observer(function TimelineApartLink(
  props: TCardProps & { apartLink: TApartLink; arrow: TScheduleArrow; heldByArrow: TScheduleArrow | undefined }
) {
  const { apartLink, arrow, heldByArrow, ...cardProps } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // translation
  const { t } = useTranslation();

  return (
    <ConflictCard
      sentence={t("timeline.apart.sentence", {
        task: getIssueById(apartLink.taskId)?.name,
        previous: getIssueById(arrow.previousId)?.name,
        days: apartLink.days,
        other: heldByArrow && getIssueById(heldByArrow.previousId)?.name,
      })}
      waysOut={[
        {
          key: "in-days",
          label: t("timeline.apart.ways_out.in-days", { days: apartLink.days }),
          change: (plan) => setArrowMode(plan, arrow.id, "in"),
        },
        {
          key: "remove-arrow",
          label: t("timeline.apart.ways_out.remove-arrow"),
          change: (plan) => removeArrow(plan, arrow.id),
        },
      ]}
      {...cardProps}
    />
  );
});
