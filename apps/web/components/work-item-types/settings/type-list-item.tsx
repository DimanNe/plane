/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Badge } from "@makeplane/propel/components/badge";
import { Collapsible } from "@makeplane/propel/components/collapsible";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { Switch } from "@makeplane/propel/components/switch";
import { ChevronDownOutline, MoreHorizontalOutline } from "@makeplane/propel/icons";
// plane imports
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TWorkItemType } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WorkItemTypeLogo } from "../type-logo";
import { WorkItemTypeSettingsDeleteModal } from "./delete-modal";
import { WorkItemPropertyList } from "./property-list";
import { WorkItemTypeFormModal } from "./type-form-modal";

type Props = {
  workspaceSlug: string;
  projectId: string;
  type: TWorkItemType;
};

export const WorkItemTypeListItem = observer(function WorkItemTypeListItem(props: Props) {
  const { workspaceSlug, projectId, type } = props;
  // states
  const [isExpanded, setIsExpanded] = useState(false);
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { updateWorkItemType, deleteWorkItemType } = useWorkItemTypes();

  const handleUpdate = (data: Partial<TWorkItemType>) =>
    updateWorkItemType(workspaceSlug, projectId, type.id, data).catch(() =>
      setToast({
        type: "error",
        title: t("work_item_types.update.toast.error.title"),
        message: t("work_item_types.update.toast.error.message.default"),
      })
    );

  return (
    <div className="rounded-md border border-subtle bg-surface-2">
      <Collapsible
        open={isExpanded}
        onOpenChange={setIsExpanded}
        indicator={false}
        icon={
          <Icon icon={<ChevronDownOutline className={cn("transition-transform", { "-rotate-90": !isExpanded })} />} />
        }
        trigger={
          <span className="flex w-full items-center gap-3 text-left">
            <WorkItemTypeLogo logoProps={type.logo_props} size={32} />
            <span className="flex min-w-0 flex-col">
              <span className="flex items-center gap-2">
                <span className="truncate text-body-sm-medium text-primary">{type.name}</span>
                {!type.is_active && (
                  <span className="text-caption-sm-regular text-tertiary">{t("common.disabled")}</span>
                )}
              </span>
              {type.description && (
                <span className="truncate text-caption-sm-regular text-tertiary">{type.description}</span>
              )}
            </span>
          </span>
        }
        trailing={
          <span className="flex items-center gap-3">
            {/* the default type cannot be disabled */}
            {type.is_default ? (
              <Badge variant="brand" size="sm" label={t("common.default")} />
            ) : (
              <Switch
                size="sm"
                aria-label={t("common.active")}
                checked={type.is_active}
                onCheckedChange={(checked) => handleUpdate({ is_active: checked })}
              />
            )}
            <Menu>
              <MenuTrigger
                render={
                  <IconButton
                    variant="ghost"
                    size="sm"
                    icon={<Icon icon={MoreHorizontalOutline} />}
                    aria-label={t("aria_labels.common.more_actions")}
                  />
                }
              />
              <MenuContent side="bottom" align="end">
                <MenuItem label={t("common.actions.edit")} onClick={() => setIsUpdateModalOpen(true)} />
                {!type.is_default && (
                  <MenuItem
                    label={t("work_item_types.settings.set_as_default")}
                    description={
                      type.is_active ? undefined : t("work_item_types.settings.cant_set_default_inactive_message")
                    }
                    disabled={!type.is_active}
                    onClick={() => handleUpdate({ is_default: true })}
                  />
                )}
                {!type.is_default && (
                  <MenuItem
                    variant="danger"
                    label={t("common.actions.delete")}
                    onClick={() => setIsDeleteModalOpen(true)}
                  />
                )}
              </MenuContent>
            </Menu>
          </span>
        }
      >
        <WorkItemPropertyList workspaceSlug={workspaceSlug} projectId={projectId} typeId={type.id} />
      </Collapsible>
      {isUpdateModalOpen && (
        <WorkItemTypeFormModal
          onClose={() => setIsUpdateModalOpen(false)}
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          type={type}
        />
      )}
      <WorkItemTypeSettingsDeleteModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onDelete={() => deleteWorkItemType(workspaceSlug, projectId, type.id)}
        title={t("work_item_types.settings.item_delete_confirmation.title")}
        content={t("work_item_types.settings.item_delete_confirmation.work_items_keep_type")}
        confirmLabel={t("work_item_types.settings.item_delete_confirmation.primary_button")}
        i18nToastPrefix="work_item_types.settings.item_delete_confirmation.toast"
      />
    </div>
  );
});
