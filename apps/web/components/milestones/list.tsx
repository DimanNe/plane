/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
// components
import { ListLayout } from "@/components/core/list";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
// local imports
import { MilestoneListItem } from "./list-item";

type Props = {
  workspaceSlug: string;
  projectId: string;
};

export const MilestonesList = observer(function MilestonesList(props: Props) {
  const { workspaceSlug, projectId } = props;
  // store hooks
  const { getFilteredMilestoneIds } = useMilestone();
  // translation
  const { t } = useTranslation();
  // derived values
  const milestoneIds = getFilteredMilestoneIds(projectId) ?? [];

  if (milestoneIds.length === 0)
    return (
      <div className="grid h-full w-full place-items-center text-body-xs-regular text-tertiary">
        {t("project_milestones.no_matching_milestones")}
      </div>
    );

  return (
    <ListLayout>
      {milestoneIds.map((milestoneId) => (
        <MilestoneListItem
          key={milestoneId}
          milestoneId={milestoneId}
          workspaceSlug={workspaceSlug}
          projectId={projectId}
        />
      ))}
    </ListLayout>
  );
});
