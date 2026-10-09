/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useFormContext } from "react-hook-form";
// plane imports
import { Select } from "@plane/blocks/select";
import type { TIssue, TWorkItemType } from "@plane/types";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WorkItemTypeLogo } from "./type-logo";

type Props = {
  // the work item the form started from, if any
  data: Partial<TIssue> | undefined;
  disabled: boolean;
  handleFormChange: () => void;
};

/**
 * The type field of the work item form. It offers the active types of the chosen project; a work item
 * keeps showing the type it has when that one is inactive.
 */
export const WorkItemTypeSelect = observer(function WorkItemTypeSelect(props: Props) {
  const { data, disabled, handleFormChange } = props;
  // form info
  const { watch, setValue } = useFormContext<TIssue>();
  // store hooks
  const { getProjectWorkItemTypes } = useWorkItemTypes();
  // derived values
  const typeId = watch("type_id");
  const types = getProjectWorkItemTypes(watch("project_id")) ?? [];

  if (types.length === 0) return null;

  return (
    <Select<TWorkItemType>
      getValues={() => types.filter((type) => type.is_active || type.id === typeId)}
      value={types.find((type) => type.id === typeId) ?? null}
      onChange={(value) => {
        if (!value || value === typeId) return;
        setValue("type_id", value, { shouldDirty: true });
        // the values of another type do not carry over; the stored ones return with the stored type
        setValue("custom_properties", value === data?.type_id ? data.custom_properties : {}, { shouldDirty: true });
        handleFormChange();
      }}
      getOptionValue={(type) => type.id}
      getOptionLabel={(type) => type.name}
      getOptionIcon={(type) => <WorkItemTypeLogo logoProps={type.logo_props} size={16} />}
      disabled={disabled}
      pinSelected={false}
    >
      <Select.Trigger variant="pill-md">
        <Select.Value />
      </Select.Trigger>
    </Select>
  );
});
