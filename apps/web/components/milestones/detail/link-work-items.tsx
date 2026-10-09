/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { ISearchIssueResponse } from "@plane/types";
// components
import { ExistingIssuesListModal } from "@/components/core/modals/existing-issues-list-modal";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";

type Props = {
  workspaceSlug: string;
  projectId: string;
  milestoneId: string;
};

export const MilestoneLinkWorkItems = observer(function MilestoneLinkWorkItems(props: Props) {
  const { workspaceSlug, projectId, milestoneId } = props;
  // states
  const [isModalOpen, setIsModalOpen] = useState(false);
  // store hooks
  const { addWorkItemsToMilestone } = useMilestone();
  // translation
  const { t } = useTranslation();

  const handleSubmit = async (workItems: ISearchIssueResponse[]) =>
    addWorkItemsToMilestone(
      workspaceSlug,
      projectId,
      milestoneId,
      workItems.map((workItem) => workItem.id)
    ).catch(() => {
      setToast({
        type: "error",
        title: t("toast.error"),
        message: t("project_milestones.toast.link_failed"),
      });
    });

  return (
    <>
      <ExistingIssuesListModal
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        isOpen={isModalOpen}
        handleClose={() => setIsModalOpen(false)}
        searchParams={{ milestone: true }}
        handleOnSubmit={handleSubmit}
      />
      <Button
        variant="primary"
        size="md"
        stretch="auto"
        label={t("project_milestones.link_work_items")}
        onClick={() => setIsModalOpen(true)}
      />
    </>
  );
});
