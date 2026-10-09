/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { omit } from "lodash-es";
import { observer } from "mobx-react";
import { useFormContext } from "react-hook-form";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EWorkItemPropertyType } from "@plane/types";
import type { TIssue } from "@plane/types";
import {
  getWorkItemFormPropertyValues,
  getWorkItemPropertyTypeKey,
  isWorkItemPropertyValueRequired,
} from "@plane/utils";
// hooks
import { useIssueModal } from "@/hooks/context/use-issue-modal";
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WORK_ITEM_PROPERTY_TYPE_ICONS } from "./property-icon";
import { WorkItemPropertyInput } from "./property-input";

type Props = {
  // the work item the form started from, if any
  data: Partial<TIssue> | undefined;
  disabled: boolean;
  isDraft: boolean;
  handleFormChange: () => void;
  onAssetUpload: (assetId: string) => void;
};

/**
 * The property fields of the work item form: those of the chosen type, each under its name. A formula has
 * nothing to enter and is left out, and so is a cascading property in a draft, as the docs have it.
 */
export const WorkItemModalProperties = observer(function WorkItemModalProperties(props: Props) {
  const { data, disabled, isDraft, handleFormChange, onAssetUpload } = props;
  // plane hooks
  const { t } = useTranslation();
  // form info
  const { watch, getValues, setValue } = useFormContext<TIssue>();
  // store hooks
  const { getWorkItemTypeProperties } = useWorkItemTypes();
  const { issuePropertyValueErrors, setIssuePropertyValueErrors } = useIssueModal();
  // derived values
  const projectId = watch("project_id");
  const typeProperties = getWorkItemTypeProperties(watch("type_id"));
  const properties = typeProperties.filter(
    (property) =>
      property.is_active &&
      property.property_type !== EWorkItemPropertyType.FORMULA &&
      !(isDraft && property.property_type === EWorkItemPropertyType.CASCADING)
  );
  const values = getWorkItemFormPropertyValues(typeProperties, watch(), data);

  if (!projectId || properties.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 py-3">
      {properties.map((property) => {
        const Icon = WORK_ITEM_PROPERTY_TYPE_ICONS[getWorkItemPropertyTypeKey(property)];
        // set by the form for an empty mandatory property, or the messages of the server that refused the value
        const error = issuePropertyValueErrors[property.id];
        return (
          <div key={property.id} className="flex items-start gap-2">
            <div className="flex h-7.5 w-2/5 shrink-0 items-center gap-1.5 text-body-xs-regular text-secondary">
              <Icon className="size-4 shrink-0" />
              <span className="truncate">{property.display_name}</span>
              {isWorkItemPropertyValueRequired(property) && <span className="text-danger-primary">*</span>}
            </div>
            <div className="flex min-w-0 grow flex-col gap-1">
              <WorkItemPropertyInput
                property={property}
                value={values[property.id]}
                onChange={(value) => {
                  setValue(
                    "custom_properties",
                    { ...getValues("custom_properties"), [property.id]: value },
                    { shouldDirty: true }
                  );
                  setIssuePropertyValueErrors(omit(issuePropertyValueErrors, property.id));
                  handleFormChange();
                }}
                variant="select-md"
                projectId={projectId}
                disabled={disabled}
                workItemId={data?.id}
                isDraft={isDraft}
                onAssetUpload={onAssetUpload}
              />
              {!!error && (
                <span className="text-caption-sm-regular text-danger-primary">
                  {Array.isArray(error)
                    ? error[0]
                    : t("common.errors.entity_required", { entity: property.display_name })}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
});
