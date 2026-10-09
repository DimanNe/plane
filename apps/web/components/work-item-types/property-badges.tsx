/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Tooltip } from "@makeplane/propel/components/tooltip";
// plane imports
import { EWorkItemPropertyType } from "@plane/types";
import type { IIssueDisplayProperties, TIssue, TWorkItemProperty } from "@plane/types";
import {
  getWorkItemPropertyKey,
  getWorkItemPropertyPath,
  getWorkItemPropertyTypeKey,
  isWorkItemPropertyDisplayProperty,
  isWorkItemPropertyReadOnlyText,
  renderFormattedDate,
} from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WORK_ITEM_PROPERTY_TYPE_ICONS } from "./property-icon";

type Props = {
  issue: TIssue;
  displayProperties: IIssueDisplayProperties | undefined;
};

/** The custom properties a layout has switched on, as read-only badges on a list row or a board card. */
export const WorkItemPropertyBadges = observer(function WorkItemPropertyBadges(props: Props) {
  const { issue, displayProperties } = props;
  // store hooks
  const { getWorkItemTypeProperties } = useWorkItemTypes();
  const { getUserDetails } = useMember();

  // What a badge says: names in place of ids, a date in the format of its property, nothing for an empty value.
  const getValueText = (property: TWorkItemProperty): string | undefined => {
    if (isWorkItemPropertyReadOnlyText(property)) return property.default_value[0];
    const value =
      property.property_type === EWorkItemPropertyType.FORMULA
        ? issue.formula_values?.[property.id]
        : issue.custom_properties?.[property.id];
    if (value === undefined || value === null || value === "" || value === false) return undefined;
    const values = Array.isArray(value) ? value : [value];
    switch (getWorkItemPropertyTypeKey(property)) {
      case "OPTION":
        return values.map((id) => property.options.find((option) => option.id === id)?.name).join(", ");
      case "CASCADING":
        return getWorkItemPropertyPath(property, value);
      case "RELATION_USER":
        return values.map((id) => getUserDetails(String(id))?.display_name).join(", ");
      case "DATETIME":
        return renderFormattedDate(String(value), property.settings.display_format);
      case "BOOLEAN":
        return property.display_name;
      default:
        return String(value);
    }
  };

  return (
    <>
      {getWorkItemTypeProperties(issue.type_id)
        .filter((property) => isWorkItemPropertyDisplayProperty(property))
        .filter((property) => displayProperties?.[getWorkItemPropertyKey(property.id)])
        .map((property) => {
          const text = getValueText(property);
          if (!text) return null;
          const Icon = WORK_ITEM_PROPERTY_TYPE_ICONS[getWorkItemPropertyTypeKey(property)];
          return (
            <Tooltip key={property.id} label={`${property.display_name}: ${text}`}>
              <div className="flex h-5 max-w-40 shrink-0 items-center gap-1.5 rounded-sm border-[0.5px] border-strong px-2.5 py-1">
                <Icon className="size-3 shrink-0" />
                <span className="truncate text-caption-sm-regular">{text}</span>
              </div>
            </Tooltip>
          );
        })}
    </>
  );
});
