/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { Popover, PopoverContent, PopoverTrigger } from "@makeplane/propel/components/popover";
import { WorkItemsOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// components
import { getDayOfDate, getDayX, TimelineViewContext } from "@/components/timeline/scale";
// helpers
import { getMilestoneState } from "@/helpers/milestone.helper";
import type { TMilestoneState } from "@/helpers/milestone.helper";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useProject } from "@/hooks/store/use-project";
// local imports
import { MilestoneProgress, MilestoneStateIcon } from "./progress";

const MILESTONE_STATE_CLASSNAMES: Record<TMilestoneState, string> = {
  not_started: "text-icon-states-unstarted",
  in_progress: "text-icon-states-started",
  done: "text-icon-states-completed",
};

/** Marks the target date of every milestone of the project on the timeline of its work items. */
export const MilestoneTimelineMarkers = observer(function MilestoneTimelineMarkers() {
  // router
  const { projectId } = useParams();
  // context
  const view = useContext(TimelineViewContext);
  // store hooks
  const { getProjectById } = useProject();
  const { getProjectMilestones } = useMilestone();
  // translation
  const { t } = useTranslation();
  // derived values
  const project = getProjectById(projectId?.toString());

  if (!project?.milestone_view) return null;

  return (
    <>
      {getProjectMilestones(project.id)?.map((milestone) => {
        if (!milestone.target_date) return null;

        return (
          <div
            key={milestone.id}
            className={cn(
              "pointer-events-none absolute top-0 z-[4] h-full border-l border-dashed border-current",
              MILESTONE_STATE_CLASSNAMES[getMilestoneState(milestone)]
            )}
            // the line stands at the end of the target date
            style={{ left: getDayX(view, getDayOfDate(milestone.target_date) + 1) }}
          >
            <Popover>
              <PopoverTrigger
                openOnHover
                delay={100}
                render={
                  <div className="pointer-events-auto absolute top-3 left-0 -translate-x-1/2 rounded-sm bg-surface-1">
                    <MilestoneStateIcon milestone={milestone} className="size-4" />
                  </div>
                }
              />
              <PopoverContent side="right" align="start" sideOffset={8}>
                <div className="w-56 space-y-2">
                  <h6 className="truncate text-body-sm-medium text-primary">{milestone.title}</h6>
                  <MilestoneProgress milestone={milestone} label={t("common.progress")} />
                  <div className="flex items-center gap-2 text-body-xs-regular text-secondary">
                    <WorkItemsOutline className="size-4 flex-shrink-0" />
                    <span>
                      {milestone.total_issues} {t("issue.label", { count: milestone.total_issues }).toLowerCase()}
                    </span>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          </div>
        );
      })}
    </>
  );
});
