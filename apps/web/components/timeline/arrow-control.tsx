/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { Popover } from "@base-ui/react/popover";
// plane imports
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { DeleteOutline } from "@makeplane/propel/icons";
import { DateSelect } from "@plane/blocks/property-select";
import { changeArrow, fixNextTask, removeArrow } from "@plane/blocks/timeline-schedule";
import type { TPlan, TSchedule, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import type { EStartOfTheWeek } from "@plane/types";
import { cn, getDate, renderFormattedPayloadDate } from "@plane/utils";
// local imports
import type { TNextTaskSide } from "./arrows";
import type { TTimelineOperation } from "./operation";

type Props = {
  arrow: TScheduleArrow;
  schedule: TSchedule;
  // the next task of the arrow is fixed on a day; else it follows its arrows
  isNextFixed: boolean;
  operation: TTimelineOperation;
  weekStartsOn: EStartOfTheWeek;
  nextTaskSide: TNextTaskSide;
  // the element of the timeline: the control stays in it
  boundary: HTMLElement | null;
  onClose: () => void;
};

// One of the things of the control. Each stands on its own with the timeline between them, so each is solid:
// it reads over a bar, a band or an arrow. The choice that holds has the accent colour.
const ITEM_CLASS_NAME =
  "flex h-6 items-center gap-1 rounded-md border border-strong bg-surface-1 px-2 text-body-xs-regular text-secondary shadow-raised-100 hover:text-primary data-[chosen=true]:border-accent-strong data-[chosen=true]:bg-accent-subtle data-[chosen=true]:text-primary";

/**
 * The control of the selected arrow, at the arrow: "immediately", "in n d", "on a date", and under them the
 * removal of the arrow, one under the other with no panel behind them. A choice is shown on the timeline at once
 * as one operation, which is saved when the control closes (Enter, a press elsewhere) and dropped on Escape.
 * The Delete key removes the arrow.
 *
 * It stands beside the arrow on the side where the bar of the next task is not, and from the arrow's last turn it
 * reaches towards the line of the next task and past it, never towards the previous one. So it lies on neither of
 * the two bars the arrow connects, unless the edge of the timeline leaves it no room on that side.
 */
export function TimelineArrowControl(props: Props) {
  const { arrow, schedule, isNextFixed, operation, weekStartsOn, nextTaskSide, boundary, onClose } = props;
  // refs
  const itemsRef = useRef<HTMLDivElement>(null);
  const dateRef = useRef<HTMLDivElement>(null);
  // the plan the operation began with, once a choice has begun one
  const begunPlanRef = useRef<TPlan>(undefined);
  // states
  const [anchor, setAnchor] = useState<HTMLSpanElement | null>(null);
  // the number as it is typed, while it is no number of days yet
  const [typedDays, setTypedDays] = useState<string>();
  // translation
  const { t } = useTranslation();
  // derived values
  const gap = schedule.gaps[arrow.id];
  const day = schedule.dates[arrow.nextId]?.[arrow.kind === "end-end" ? "end" : "start"];
  const isImmediate = !isNextFixed && arrow.delay === 0;
  const isDelayed = !isNextFixed && arrow.delay > 0;
  // "in n d" offers the delay of the arrow; of an arrow that asks "immediately", the gap there is now
  const days = arrow.delay || Math.max(gap, 1);

  const show = (getChangedPlan: (begunPlan: TPlan) => TPlan) => {
    begunPlanRef.current ??= operation.begin();
    if (begunPlanRef.current) operation.preview(getChangedPlan(begunPlanRef.current));
  };

  const close = (isAborted: boolean) => {
    if (begunPlanRef.current && isAborted) operation.abort();
    else if (begunPlanRef.current) operation.commit();
    begunPlanRef.current = undefined;
    onClose();
  };

  const remove = () => {
    show((plan) => removeArrow(plan, arrow.id));
    close(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    // the keys of what opens from the control, the calendar, arrive here too
    if (!(e.target instanceof HTMLElement) || !e.currentTarget.contains(e.target)) return;
    if (e.key === "Delete" && !(e.target instanceof HTMLInputElement)) remove();
    // Enter on the date opens the calendar; anywhere else it makes the choice it is on and saves
    if (e.key !== "Enter" || dateRef.current?.contains(e.target)) return;
    e.preventDefault();
    if (e.target instanceof HTMLButtonElement) e.target.click();
    close(false);
  };

  // a control that goes away while its operation is going on, with its arrow or with the timeline, drops it
  useEffect(
    () => () => {
      if (begunPlanRef.current) operation.abort();
    },
    [operation]
  );

  return (
    <>
      <span ref={setAnchor} />
      {anchor && (
        // open, the control takes every press: one elsewhere closes it and does nothing else
        <Popover.Root open modal onOpenChange={(_open, details) => close(details.reason === "escape-key")}>
          <Popover.Portal>
            <Popover.Positioner
              className="z-50"
              anchor={anchor}
              side={nextTaskSide.isRight ? "left" : "right"}
              align={nextTaskSide.isBelow ? "start" : "end"}
              sideOffset={8}
              // clear of the text of the arrow, which often stands at this place
              alignOffset={10}
              collisionBoundary={boundary ?? undefined}
            >
              <Popover.Popup
                ref={itemsRef}
                // each thing keeps to the arrow, whichever side of it they stand on
                className="flex flex-col gap-1 outline-none select-text data-[side=left]:items-end data-[side=right]:items-start"
                initialFocus={itemsRef}
                onKeyDown={handleKeyDown}
              >
                <button
                  type="button"
                  className={ITEM_CLASS_NAME}
                  data-chosen={isImmediate}
                  aria-pressed={isImmediate}
                  onClick={() => show((plan) => changeArrow(plan, arrow.id, { delay: 0 }))}
                >
                  {t("timeline.arrow.immediately")}
                </button>
                <div className={ITEM_CLASS_NAME} data-chosen={isDelayed}>
                  <button
                    type="button"
                    aria-pressed={isDelayed}
                    onClick={() => show((plan) => changeArrow(plan, arrow.id, { delay: days }))}
                  >
                    {t("timeline.arrow.in")}
                  </button>
                  <input
                    type="number"
                    min={1}
                    aria-label={t("timeline.arrow.delay")}
                    className="w-10 rounded-sm border border-subtle bg-surface-1 px-1 text-center text-primary outline-none focus:border-accent-strong"
                    value={typedDays ?? days}
                    onChange={(e) => {
                      const delay = Math.round(Number(e.target.value));
                      setTypedDays(delay >= 1 ? undefined : e.target.value);
                      if (delay >= 1) show((plan) => changeArrow(plan, arrow.id, { delay }));
                    }}
                    onBlur={() => setTypedDays(undefined)}
                  />
                  {t("timeline.arrow.days")}
                </div>
                <div ref={dateRef} className={ITEM_CLASS_NAME} data-chosen={isNextFixed}>
                  <button
                    type="button"
                    aria-pressed={isNextFixed}
                    onClick={() => day && show((plan) => fixNextTask(plan, arrow.id, day))}
                  >
                    {t("timeline.arrow.on")}
                  </button>
                  <DateSelect
                    value={getDate(day) ?? null}
                    onChange={(date) => {
                      const pickedDay = renderFormattedPayloadDate(date);
                      if (pickedDay) show((plan) => fixNextTask(plan, arrow.id, pickedDay));
                    }}
                    weekStartsOn={weekStartsOn}
                    variant="pill-sm"
                  />
                </div>
                <Tooltip label={t("timeline.arrow.remove")}>
                  <button
                    type="button"
                    aria-label={t("timeline.arrow.remove")}
                    // apart from the three choices
                    className={cn(ITEM_CLASS_NAME, "mt-1.5 hover:border-danger-strong hover:text-danger-primary")}
                    onClick={remove}
                  >
                    <DeleteOutline className="size-3.5" />
                  </button>
                </Tooltip>
              </Popover.Popup>
            </Popover.Positioner>
          </Popover.Portal>
        </Popover.Root>
      )}
    </>
  );
}
