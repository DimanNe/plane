/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TMilestone } from "@plane/types";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";

type Props = {
  milestone: TMilestone;
  isOpen: boolean;
  handleClose: () => void;
  workspaceSlug: string;
  projectId: string;
};

export const MilestoneDeleteModal = observer(function MilestoneDeleteModal(props: Props) {
  const { milestone, isOpen, handleClose, workspaceSlug, projectId } = props;
  // states
  const [isSubmitting, setIsSubmitting] = useState(false);
  // store hooks
  const { deleteMilestone } = useMilestone();
  // translation
  const { t } = useTranslation();

  const handleSubmit = async () => {
    setIsSubmitting(true);
    await deleteMilestone(workspaceSlug, projectId, milestone.id)
      .then(() =>
        setToast({
          type: "success",
          title: t("toast.success"),
          message: t("project_milestones.toast.deleted"),
        })
      )
      .catch(() =>
        setToast({
          type: "error",
          title: t("toast.error"),
          message: t("project_milestones.toast.delete_failed"),
        })
      )
      .finally(() => {
        setIsSubmitting(false);
        handleClose();
      });
  };

  return (
    <ConfirmDialog
      handleClose={handleClose}
      handleSubmit={handleSubmit}
      isSubmitting={isSubmitting}
      isOpen={isOpen}
      title={t("project_milestones.delete_milestone")}
      content={t("project_milestones.delete_confirmation", { title: milestone.title })}
    />
  );
});
