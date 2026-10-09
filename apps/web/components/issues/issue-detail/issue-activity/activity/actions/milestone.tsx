/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import Link from "next/link";
// plane imports
import { MilestoneOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// components
import { IssueActivityBlockComponent } from "./";

type TIssueMilestoneActivity = { activityId: string; ends: "top" | "bottom" | undefined };

export const IssueMilestoneActivity = observer(function IssueMilestoneActivity(props: TIssueMilestoneActivity) {
  const { activityId, ends } = props;
  // hooks
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  // translation
  const { t } = useTranslation();

  const activity = getActivityById(activityId);

  if (!activity) return <></>;

  // the work item is in the new milestone, or was removed from the old one
  const milestoneId = activity.new_identifier ?? activity.old_identifier;

  return (
    <IssueActivityBlockComponent
      icon={<MilestoneOutline className="h-4 w-4 flex-shrink-0 text-secondary" />}
      activityId={activityId}
      ends={ends}
    >
      <span>
        {activity.new_identifier
          ? t("project_milestones.activity.set_milestone")
          : t("project_milestones.activity.removed_from_milestone")}{" "}
      </span>
      <Link
        href={`/${activity.workspace_detail?.slug}/projects/${activity.project}/overview/milestones/${milestoneId}`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 truncate font-medium text-primary hover:underline"
      >
        <span className="truncate">{activity.new_value ?? activity.old_value}</span>
      </Link>
    </IssueActivityBlockComponent>
  );
});
