/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import type { TConflict, TScheduleArrow, TWayOut } from "@plane/blocks/timeline-schedule";
import { useTranslation } from "@plane/i18n";
import { renderFormattedDate } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";

type Props = {
  conflict: TConflict;
  arrow: TScheduleArrow;
  // not given when the plan cannot be changed: the ways out are then not offered
  onWayOut?: (wayOut: TWayOut) => void;
};

const formatDay = (day: string) => renderFormattedDate(day, "MMM d");

/** Why an arrow is a conflict, in a sentence made of the conflict the schedule reports, and the ways out of it. */
export const TimelineConflict = observer(function TimelineConflict(props: Props) {
  const { conflict, arrow, onWayOut } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // translation
  const { t } = useTranslation();

  return (
    <>
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
      {onWayOut && (
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
              onClick={() => onWayOut(wayOut)}
            />
          ))}
        </div>
      )}
    </>
  );
});
