/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
// components
import { WorkItemsTimeline } from "@/components/timeline/root";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useUserPermissions } from "@/hooks/store/user";

type Props = {
  milestoneId: string;
};

export const MilestoneWorkItemsTimeline = observer(function MilestoneWorkItemsTimeline(props: Props) {
  const { milestoneId } = props;
  // states
  const [showOnlyLeaves, setShowOnlyLeaves] = useState(false);
  // store hooks
  const { getMilestoneById, getMilestoneWorkItemIds } = useMilestone();
  const { allowPermissions } = useUserPermissions();
  // derived values
  const milestone = getMilestoneById(milestoneId);
  const workItemIds = getMilestoneWorkItemIds(milestoneId);
  const isEditingAllowed = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT
  );

  return (
    <div className="h-full w-full">
      <WorkItemsTimeline
        workItemIds={workItemIds}
        focusDate={milestone?.target_date}
        isEditable={isEditingAllowed}
        showOnlyLeaves={showOnlyLeaves}
        onShowOnlyLeavesChange={setShowOnlyLeaves}
      />
    </div>
  );
});
