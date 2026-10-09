/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { WorkItemsOutline } from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EWorkItemPropertyType } from "@plane/types";
import { getWorkItemPropertyTypeKey, renderFormattedDate } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// components
import { WORK_ITEM_PROPERTY_TYPE_ICONS } from "@/components/work-item-types/property-icon";
import { IssueActivityBlockComponent } from "./";

type TIssueCustomPropertyActivity = { activityId: string; ends: "top" | "bottom" | undefined };

/**
 * A change of the work item type or of the value of a custom property. The activity says in its comment
 * what was updated and has the new value as text; a date is shown in the format of its property.
 */
export const IssueCustomPropertyActivity = observer(function IssueCustomPropertyActivity(
  props: TIssueCustomPropertyActivity
) {
  const { activityId, ends } = props;
  // plane hooks
  const { t } = useTranslation();
  // hooks
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const { getWorkItemPropertyByKey } = useWorkItemTypes();

  const activity = getActivityById(activityId);

  if (!activity) return <></>;

  const property = activity.field === "type" ? undefined : getWorkItemPropertyByKey(activity.new_identifier ?? "");
  const Icon = property ? WORK_ITEM_PROPERTY_TYPE_ICONS[getWorkItemPropertyTypeKey(property)] : WorkItemsOutline;
  const newValue =
    property?.property_type === EWorkItemPropertyType.DATETIME
      ? renderFormattedDate(activity.new_value, property.settings.display_format)
      : activity.new_value;

  return (
    <IssueActivityBlockComponent
      icon={<Icon className="h-3.5 w-3.5 text-secondary" aria-hidden="true" />}
      activityId={activityId}
      ends={ends}
    >
      <>
        {activity.comment}
        <span className="font-medium text-primary">{newValue || t("common.none")}</span>.
      </>
    </IssueActivityBlockComponent>
  );
});
