/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Button } from "@makeplane/propel/components/button";
// plane imports
import { ConfirmDialog } from "@plane/blocks/dialog";
import { EmptyStateCompact } from "@plane/blocks/empty-state";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
// components
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WorkItemTypeFormModal } from "./type-form-modal";
import { WorkItemTypeListItem } from "./type-list-item";

type Props = {
  workspaceSlug: string;
  projectId: string;
};

export const WorkItemTypesRoot = observer(function WorkItemTypesRoot(props: Props) {
  const { workspaceSlug, projectId } = props;
  // states
  const [isEnableConfirmationOpen, setIsEnableConfirmationOpen] = useState(false);
  const [isEnabling, setIsEnabling] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getProjectById } = useProject();
  const { getProjectWorkItemTypes, enableWorkItemTypes } = useWorkItemTypes();
  // derived values
  const types = getProjectWorkItemTypes(projectId) ?? [];

  const handleEnable = async () => {
    setIsEnabling(true);
    try {
      await enableWorkItemTypes(workspaceSlug, projectId);
      setIsEnableConfirmationOpen(false);
    } catch {
      setToast({
        type: "error",
        title: t("common.errors.default.title"),
        message: t("common.errors.default.message"),
      });
    } finally {
      setIsEnabling(false);
    }
  };

  if (!getProjectById(projectId)?.is_issue_type_enabled)
    return (
      <>
        <EmptyStateCompact
          assetKey="work-item"
          assetClassName="size-20"
          title={t("work_item_types.empty_state.enable.title")}
          description={t("work_item_types.empty_state.enable.description")}
          actions={[
            {
              label: t("work_item_types.empty_state.enable.primary_button.text"),
              onClick: () => setIsEnableConfirmationOpen(true),
            },
          ]}
          align="start"
          rootClassName="py-20"
        />
        <ConfirmDialog
          isOpen={isEnableConfirmationOpen}
          handleClose={() => setIsEnableConfirmationOpen(false)}
          handleSubmit={handleEnable}
          isSubmitting={isEnabling}
          title={t("work_item_types.empty_state.enable.confirmation.title")}
          content={t("work_item_types.empty_state.enable.confirmation.description")}
          primaryButtonText={{
            loading: t("work_item_types.empty_state.enable.confirmation.button.loading"),
            default: t("work_item_types.empty_state.enable.confirmation.button.default"),
          }}
          variant="warning"
        />
      </>
    );

  return (
    <>
      <SettingsHeading
        title={t("work_item_types.label")}
        description={t("work_item_types.settings.types.description")}
        control={
          <Button
            variant="primary"
            size="md"
            stretch="auto"
            onClick={() => setIsCreateModalOpen(true)}
            label={t("work_item_types.create.button")}
          />
        }
      />
      <div className="mt-6 flex flex-col gap-2">
        {types.map((type) => (
          <WorkItemTypeListItem key={type.id} workspaceSlug={workspaceSlug} projectId={projectId} type={type} />
        ))}
      </div>
      {isCreateModalOpen && (
        <WorkItemTypeFormModal
          onClose={() => setIsCreateModalOpen(false)}
          workspaceSlug={workspaceSlug}
          projectId={projectId}
        />
      )}
    </>
  );
});
