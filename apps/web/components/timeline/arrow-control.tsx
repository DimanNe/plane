/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ComponentProps } from "react";
import { useEffect, useRef, useState } from "react";
// plane imports
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Popover, PopoverContent } from "@makeplane/propel/components/popover";
import { DeleteOutline } from "@makeplane/propel/icons";
import { DateSelect } from "@plane/blocks/property-select";
import { applyWayOut, changeArrow, fixNextTask, removeArrow } from "@plane/blocks/timeline-schedule";
import type { TConflict, TPlan, TSchedule, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import type { EStartOfTheWeek } from "@plane/types";
import { cn, getDate, renderFormattedDate, renderFormattedPayloadDate } from "@plane/utils";
// local imports
import { TimelineConflict } from "./conflict";
import type { TTimelineOperation } from "./operation";

type TArrowFacts = {
  arrow: TScheduleArrow;
  schedule: TSchedule;
  // the next task of the arrow is fixed on a day; else it follows its arrows
  isNextFixed: boolean;
};

type TChipProps = TArrowFacts & ComponentProps<"button">;

type TControlProps = TArrowFacts & {
  previousName: string;
  // the conflict the arrow is, which the control then explains and offers the ways out of
  conflict: TConflict | undefined;
  operation: TTimelineOperation;
  weekStartsOn: EStartOfTheWeek;
  // the choices can be made; else the control only tells
  isEditable: boolean;
  // the choices are shown; else the control is what a pointer over the arrow shows
  isOpen: boolean;
  // where the choices open: clear of the next task, which they move
  openSide: "top" | "bottom";
  onOpen: () => void;
  onClose: () => void;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
};

// a choice of the control, and the choice that holds now
const CHOICE_CLASS_NAME =
  "flex h-6 items-center gap-1 rounded-md px-1.5 text-body-xs-regular text-secondary hover:bg-layer-transparent-hover data-[chosen=true]:bg-layer-transparent-selected data-[chosen=true]:text-primary";

/** The edge of its next task that an arrow constrains, as the word for what the task does there. */
const getVerbKey = (arrow: TScheduleArrow) => `timeline.arrow.${arrow.kind === "end-end" ? "ends" : "starts"}`;

/**
 * What an arrow says at a glance: "starts: in 3 d", or "on Oct 12" when its next task is fixed. An arrow that
 * does not decide where its next task stands also says the gap there is now, and what it asks of a fixed task.
 * The arrow that decides reads strong, a conflict red, the others faint.
 */
export function TimelineArrowChip(props: TChipProps) {
  const { arrow, schedule, isNextFixed, className, ...buttonProps } = props;
  // translation
  const { t } = useTranslation();
  // derived values
  const gap = schedule.gaps[arrow.id];
  const delay =
    arrow.delay === 0 ? t("timeline.arrow.immediately") : t("timeline.arrow.in_days", { days: arrow.delay });
  const day = schedule.dates[arrow.nextId]?.[arrow.kind === "end-end" ? "end" : "start"];
  const isConflict = schedule.conflicts.some((conflict) => conflict.arrowId === arrow.id);
  const isDeciding = schedule.decidingArrowId[arrow.nextId] === arrow.id;

  return (
    <button
      type="button"
      className={cn(
        "flex h-5 items-center gap-1 rounded-sm border bg-surface-1 px-1.5 text-caption-md-regular whitespace-nowrap text-tertiary shadow-raised-100",
        isConflict ? "border-danger-strong" : isDeciding ? "border-strong" : "border-subtle-1",
        className
      )}
      {...buttonProps}
    >
      <span
        className={cn({
          "text-caption-md-medium text-primary": isDeciding,
          "text-caption-md-medium text-danger-primary": isConflict,
        })}
      >
        {t(getVerbKey(arrow))}:{" "}
        {isNextFixed ? t("timeline.arrow.on_day", { day: renderFormattedDate(day, "MMM d") }) : delay}
      </span>
      {isNextFixed && <span>· {t("timeline.arrow.asks", { delay })}</span>}
      {(isNextFixed || gap !== arrow.delay) && <span>· {t("timeline.arrow.gap", { days: gap })}</span>}
    </button>
  );
}

/**
 * The control of an arrow, at the arrow. Open, it offers "immediately", "in n d" and "on a date", and the removal
 * of the arrow; each choice is shown on the timeline at once as one operation, which is saved when the control
 * closes and dropped on Escape. Of a conflict it tells the reason and offers the ways out, also before it is open.
 */
export function TimelineArrowControl(props: TControlProps) {
  const {
    arrow,
    schedule,
    isNextFixed,
    previousName,
    conflict,
    operation,
    weekStartsOn,
    isEditable,
    isOpen,
    openSide,
    onOpen,
    onClose,
    onPointerEnter,
    onPointerLeave,
  } = props;
  // refs
  const choicesRef = useRef<HTMLDivElement>(null);
  // the plan the operation began with, once a choice has begun one, and the plan it shows now
  const begunPlanRef = useRef<TPlan>(undefined);
  const shownPlanRef = useRef<TPlan>(undefined);
  // states
  const [chip, setChip] = useState<HTMLButtonElement | null>(null);
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

  /** A choice changes the plan the operation began with; a way out of a conflict, the plan that shows it. */
  const show = (getChangedPlan: (begunPlan: TPlan, shownPlan: TPlan) => TPlan) => {
    begunPlanRef.current ??= operation.begin();
    if (!begunPlanRef.current) return;
    shownPlanRef.current = getChangedPlan(begunPlanRef.current, shownPlanRef.current ?? begunPlanRef.current);
    operation.preview(shownPlanRef.current);
  };

  const close = (isAborted: boolean) => {
    if (begunPlanRef.current && isAborted) operation.abort();
    else if (begunPlanRef.current) operation.commit();
    begunPlanRef.current = undefined;
    onClose();
  };

  // a control that goes away while its operation is going on, with its arrow or under a drag, drops the operation
  useEffect(
    () => () => {
      if (begunPlanRef.current) operation.abort();
    },
    [operation]
  );

  return (
    <>
      <TimelineArrowChip
        ref={setChip}
        arrow={arrow}
        schedule={schedule}
        isNextFixed={isNextFixed}
        aria-expanded={isOpen}
        onClick={() => isEditable && !isOpen && onOpen()}
        onPointerEnter={onPointerEnter}
        onPointerLeave={onPointerLeave}
      />
      {chip && (isOpen || conflict) && (
        // open, the control takes every press: one elsewhere closes it and does nothing else
        <Popover open modal={isOpen} onOpenChange={(_open, details) => close(details.reason === "escape-key")}>
          <PopoverContent
            anchor={chip}
            side={openSide}
            // to the right of the arrow: what decides where its next task stands is before it, to the left
            align="start"
            sideOffset={6}
            // the keys go to the choices; a control that only tells leaves the focus where it is
            initialFocus={isOpen ? choicesRef : false}
            onPointerEnter={onPointerEnter}
            onPointerLeave={onPointerLeave}
          >
            <div className="flex max-w-96 flex-col gap-2">
              {isOpen && (
                <div
                  ref={choicesRef}
                  role="group"
                  tabIndex={-1}
                  className="flex flex-wrap items-center gap-1 outline-none"
                  onKeyDown={(e) => e.key === "Enter" && !(e.target instanceof HTMLButtonElement) && close(false)}
                >
                  <span className="pr-1 text-body-xs-medium text-primary">{t(getVerbKey(arrow))}:</span>
                  <button
                    type="button"
                    className={CHOICE_CLASS_NAME}
                    data-chosen={isImmediate}
                    aria-pressed={isImmediate}
                    onClick={() => show((plan) => changeArrow(plan, arrow.id, { delay: 0 }))}
                  >
                    {t("timeline.arrow.immediately")}
                  </button>
                  <div className={CHOICE_CLASS_NAME} data-chosen={isDelayed}>
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
                  <div className={CHOICE_CLASS_NAME} data-chosen={isNextFixed}>
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
                  <IconButton
                    variant="ghost"
                    size="md"
                    icon={<Icon icon={DeleteOutline} />}
                    aria-label={t("timeline.arrow.remove")}
                    onClick={() => {
                      show((plan) => removeArrow(plan, arrow.id));
                      close(false);
                    }}
                  />
                  <div className="w-full text-caption-md-regular text-tertiary">
                    {t(`timeline.arrow.after.${arrow.kind}`, { task: previousName })}
                  </div>
                </div>
              )}
              {conflict && (
                <TimelineConflict
                  conflict={conflict}
                  arrow={arrow}
                  onWayOut={
                    isEditable
                      ? (wayOut) => {
                          show((_, shownPlan) => applyWayOut(shownPlan, conflict, wayOut));
                          close(false);
                        }
                      : undefined
                  }
                />
              )}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </>
  );
}
