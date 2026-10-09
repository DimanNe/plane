/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { AddOutline, InfoOutline } from "@makeplane/propel/icons";
// plane imports
import { Sortable } from "@plane/blocks/common";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TWorkItemProperty } from "@plane/types";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WorkItemPropertyFormModal } from "./property-form-modal";
import { WorkItemPropertyListItem } from "./property-list-item";

type Props = {
  workspaceSlug: string;
  projectId: string;
  typeId: string;
};

export const WorkItemPropertyList = observer(function WorkItemPropertyList(props: Props) {
  const { workspaceSlug, projectId, typeId } = props;
  // states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getWorkItemTypeProperties, updateWorkItemProperty } = useWorkItemTypes();
  // derived values
  const properties = getWorkItemTypeProperties(typeId);
  const i18nPrefix = "work_item_types.settings.properties";

  // A moved property takes a sort order between those of its new neighbours.
  const handleMove = (orderedProperties: TWorkItemProperty[], movedProperty?: TWorkItemProperty) => {
    const index = orderedProperties.findIndex((property) => property.id === movedProperty?.id);
    if (!movedProperty || index === -1) return;
    const previous = orderedProperties[index - 1]?.sort_order;
    const next = orderedProperties[index + 1]?.sort_order;
    const sortOrder =
      previous !== undefined && next !== undefined
        ? (previous + next) / 2
        : previous !== undefined
          ? previous + 10000
          : (next ?? movedProperty.sort_order) / 2;
    updateWorkItemProperty(workspaceSlug, projectId, movedProperty.id, { sort_order: sortOrder }).catch(() =>
      setToast({
        type: "error",
        title: t(`${i18nPrefix}.toast.update.error.title`),
        message: t(`${i18nPrefix}.toast.update.error.message`),
      })
    );
  };

  return (
    <div className="flex flex-col gap-3 px-2 pb-2">
      <div className="flex items-center gap-1.5 text-body-sm-medium text-secondary">
        {t(`${i18nPrefix}.title`)}
        <Tooltip label={t(`${i18nPrefix}.tooltip`)} layout="stacked">
          <span className="grid place-items-center text-tertiary">
            <InfoOutline className="size-3.5" />
          </span>
        </Tooltip>
      </div>
      {properties.length === 0 ? (
        <p className="text-body-xs-regular text-tertiary">{t(`${i18nPrefix}.empty_state.description`)}</p>
      ) : (
        <Sortable
          data={properties}
          keyExtractor={(property) => property.id}
          containerClassName="mb-2"
          onChange={handleMove}
          render={(property) => (
            <WorkItemPropertyListItem workspaceSlug={workspaceSlug} projectId={projectId} property={property} />
          )}
        />
      )}
      <div>
        <Button
          variant="secondary"
          size="sm"
          stretch="auto"
          icon={<Icon icon={AddOutline} />}
          label={t(`${i18nPrefix}.add_button`)}
          onClick={() => setIsCreateModalOpen(true)}
        />
      </div>
      {isCreateModalOpen && (
        <WorkItemPropertyFormModal
          onClose={() => setIsCreateModalOpen(false)}
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          typeId={typeId}
        />
      )}
    </div>
  );
});
