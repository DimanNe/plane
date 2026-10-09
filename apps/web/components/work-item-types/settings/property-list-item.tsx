/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Badge } from "@makeplane/propel/components/badge";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { MoreHorizontalOutline } from "@makeplane/propel/icons";
// plane imports
import { DragHandle } from "@plane/blocks/common";
import { WORK_ITEM_PROPERTY_TYPES } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TWorkItemProperty } from "@plane/types";
import { getWorkItemPropertyTypeKey, isWorkItemPropertyValueRequired } from "@plane/utils";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WORK_ITEM_PROPERTY_TYPE_ICONS } from "../property-icon";
import { WorkItemTypeSettingsDeleteModal } from "./delete-modal";
import { WorkItemPropertyFormModal } from "./property-form-modal";

type Props = {
  workspaceSlug: string;
  projectId: string;
  property: TWorkItemProperty;
};

export const WorkItemPropertyListItem = observer(function WorkItemPropertyListItem(props: Props) {
  const { workspaceSlug, projectId, property } = props;
  // states
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { deleteWorkItemProperty } = useWorkItemTypes();
  // derived values
  const typeKey = getWorkItemPropertyTypeKey(property);
  const TypeIcon = WORK_ITEM_PROPERTY_TYPE_ICONS[typeKey];
  const canSelectMany = typeKey === "OPTION" || typeKey === "RELATION_USER";

  return (
    <div className="flex items-center gap-2 rounded-md border border-subtle bg-surface-1 px-2 py-1.5">
      <DragHandle className="bg-transparent" />
      <TypeIcon className="size-4 shrink-0 text-tertiary" />
      <span className="min-w-0 grow truncate text-body-xs-medium text-primary">
        {property.display_name}
        {isWorkItemPropertyValueRequired(property) && <span className="pl-0.5 text-danger-primary">*</span>}
      </span>
      <Badge
        variant="neutral"
        size="sm"
        label={
          canSelectMany
            ? t(
                `work_item_types.settings.properties.attributes.relation.${property.is_multi ? "multi_select" : "single_select"}.label`
              )
            : t(WORK_ITEM_PROPERTY_TYPES[typeKey].i18n_label)
        }
      />
      <Badge
        variant={property.is_active ? "success" : "neutral"}
        size="sm"
        label={t(property.is_active ? "common.active" : "common.disabled")}
      />
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
          <MenuItem variant="danger" label={t("common.actions.delete")} onClick={() => setIsDeleteModalOpen(true)} />
        </MenuContent>
      </Menu>
      {isUpdateModalOpen && (
        <WorkItemPropertyFormModal
          onClose={() => setIsUpdateModalOpen(false)}
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          typeId={property.issue_type}
          property={property}
        />
      )}
      <WorkItemTypeSettingsDeleteModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onDelete={() => deleteWorkItemProperty(workspaceSlug, projectId, property.id)}
        title={t("work_item_types.settings.properties.delete_confirmation.title")}
        content={t("work_item_types.settings.properties.delete_confirmation.description")}
        confirmLabel={t("work_item_types.settings.properties.delete_confirmation.primary_button", {
          action: t("common.yes"),
        })}
        i18nToastPrefix="work_item_types.settings.properties.toast.delete"
        name={property.display_name}
      />
    </div>
  );
});
