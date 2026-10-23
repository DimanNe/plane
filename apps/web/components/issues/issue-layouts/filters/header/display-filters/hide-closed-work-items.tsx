/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import { useLatestCallback } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";
// components
import { useWheelNotches } from "@/components/timeline/wheel";
import { FilterHeader } from "../helpers/filter-header";
import { FilterOption } from "../helpers/filter-option";

// the days a work item closed longer ago is hidden after, when the option is turned on
const DEFAULT_DAYS = 7;
// how long the wheel or the arrow keys rest before the number they changed is saved
const DAYS_REST_TIME = 800;

type Props = {
  hideClosedForMoreThanDays: number | null | undefined;
  handleUpdate: (hideClosedForMoreThanDays: number | null) => void;
};

/**
 * The Display option that hides the work items closed (completed or cancelled) for more than a number of days, so
 * that a list keeps what is still being worked on and what was closed lately. The wheel over the number changes it,
 * a day a notch, up for more, and so do the arrow keys. Each change shows at once, but turning through several days
 * is one change of the list: it is saved, and the list fetched again, when the wheel has rested.
 */
export const FilterHideClosedWorkItems = observer(function FilterHideClosedWorkItems(props: Props) {
  const { hideClosedForMoreThanDays, handleUpdate } = props;
  // hooks
  const { t } = useTranslation();
  // states
  const [previewEnabled, setPreviewEnabled] = useState(true);
  const [daysElement, setDaysElement] = useState<HTMLSpanElement | null>(null);
  // the days shown while the wheel turns them, before they are saved; the ref holds them as well, since notches can
  // come faster than the component draws them, and each must start from the one before
  const [turnedDays, setTurnedDays] = useState<number | undefined>(undefined);
  const turnedDaysRef = useRef<number>(undefined);
  const restTimerRef = useRef<number>(undefined);

  const isHiding = hideClosedForMoreThanDays !== null && hideClosedForMoreThanDays !== undefined;
  const days = turnedDays ?? hideClosedForMoreThanDays ?? DEFAULT_DAYS;

  const save = useLatestCallback(() => {
    window.clearTimeout(restTimerRef.current);
    restTimerRef.current = undefined;
    const turned = turnedDaysRef.current;
    if (turned === undefined) return;
    turnedDaysRef.current = undefined;
    setTurnedDays(undefined);
    if (turned !== hideClosedForMoreThanDays) handleUpdate(turned);
  });

  const changeDays = useLatestCallback((step: 1 | -1) => {
    // FOR_REVIEWER: 0 is the least, and hides every closed work item at once; there is no most. Besides the wheel,
    // the arrow keys change the number (it is a spinbutton); typing a number was not asked for and is not offered.
    if (!isHiding) return;
    const turned = Math.max(0, (turnedDaysRef.current ?? hideClosedForMoreThanDays ?? DEFAULT_DAYS) + step);
    turnedDaysRef.current = turned;
    setTurnedDays(turned);
    window.clearTimeout(restTimerRef.current);
    restTimerRef.current = window.setTimeout(save, DAYS_REST_TIME);
  });

  useWheelNotches(daysElement, isHiding ? changeDays : undefined);

  // a change that has not rested yet is saved when the dropdown closes
  useEffect(() => () => save(), [save]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    changeDays(event.key === "ArrowUp" ? 1 : -1);
  };

  return (
    <>
      <FilterHeader
        title={t("issue.display.closed.label")}
        isPreviewEnabled={previewEnabled}
        handleIsPreviewEnabled={() => setPreviewEnabled(!previewEnabled)}
      />
      {previewEnabled && (
        <div>
          <FilterOption
            isChecked={isHiding}
            onClick={() => handleUpdate(isHiding ? null : days)}
            title={t("issue.display.closed.hide")}
          />
          <div
            className={`flex items-center gap-2 py-1 pr-1.5 pl-6.5 text-caption-sm-regular ${
              isHiding ? "text-secondary" : "text-placeholder"
            }`}
          >
            <span>{t("issue.display.closed.closed_for_more_than")}</span>
            <span
              ref={setDaysElement}
              role="spinbutton"
              tabIndex={isHiding ? 0 : -1}
              aria-disabled={!isHiding}
              aria-label={t("issue.display.closed.closed_for_more_than")}
              aria-valuemin={0}
              aria-valuenow={days}
              aria-valuetext={t("issue.display.closed.days", { count: days })}
              onKeyDown={isHiding ? handleKeyDown : undefined}
              onBlur={save}
              className={`filters-dropdown-number rounded-full px-2 py-0.5 tabular-nums select-none ${
                isHiding ? "cursor-ns-resize text-primary" : ""
              }`}
            >
              {t("issue.display.closed.days", { count: days })}
            </span>
          </div>
        </div>
      )}
    </>
  );
});
