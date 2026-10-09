/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EWorkItemPropertyType } from "@plane/types";
import { Row } from "@plane/blocks/layout";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { IIssueDisplayProperties, TIssue, TWorkItemProperty } from "@plane/types";
import { cn, getWorkItemPropertyErrorMessage, getWorkItemPropertyTypeKey } from "@plane/utils";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WORK_ITEM_PROPERTY_TYPE_ICONS } from "./property-icon";
import { WorkItemPropertyInput } from "./property-input";

/** The table header of a custom property: its name, without the sort menu of the built-in columns. */
export function SpreadsheetWorkItemPropertyHeader(props: { property: TWorkItemProperty }) {
  const { property } = props;
  const Icon = WORK_ITEM_PROPERTY_TYPE_ICONS[getWorkItemPropertyTypeKey(property)];

  return (
    <Row className="flex items-center gap-1.5 py-2 text-13 text-secondary">
      <Icon className="h-4 w-4 shrink-0 text-placeholder" />
      <span className="truncate">{property.display_name}</span>
    </Row>
  );
}

type Props = {
  issue: TIssue;
  property: keyof IIssueDisplayProperties;
  // the table hands in its asynchronous update and reports no failure of it, so the cell does
  onChange: (issue: TIssue, data: Partial<TIssue>, updates: any) => void | Promise<void>;
  disabled: boolean;
};

/** The table cell of a custom property. A work item has a value only for the properties of its own type. */
export const SpreadsheetWorkItemPropertyColumn = observer(function SpreadsheetWorkItemPropertyColumn(props: Props) {
  const { issue, property: propertyKey, onChange, disabled } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getWorkItemPropertyByKey } = useWorkItemTypes();
  // derived values
  const property = getWorkItemPropertyByKey(propertyKey);

  if (!property || property.issue_type !== issue.type_id || !issue.project_id)
    return <div className="h-11 border-b-[0.5px] border-subtle" />;

  const isFormula = property.property_type === EWorkItemPropertyType.FORMULA;
  // a select fills the cell with its trigger; a field keeps a margin around its frame
  const isSelect = [
    EWorkItemPropertyType.OPTION,
    EWorkItemPropertyType.DATETIME,
    EWorkItemPropertyType.RELATION,
  ].includes(property.property_type);

  return (
    <div className={cn("flex h-11 items-center overflow-hidden border-b-[0.5px] border-subtle", { "px-2": !isSelect })}>
      <WorkItemPropertyInput
        property={property}
        value={(isFormula ? issue.formula_values : issue.custom_properties)?.[property.id]}
        formulaError={issue.formula_errors?.[property.id]}
        onChange={async (value) => {
          try {
            await onChange(
              issue,
              { custom_properties: { [property.id]: value } },
              { changed_property: propertyKey, change_details: value }
            );
          } catch (error) {
            setToast({
              type: "error",
              title: property.display_name,
              message:
                getWorkItemPropertyErrorMessage(error) ?? t("entity.update.failed", { entity: t("issue.label") }),
            });
          }
        }}
        variant="table-cell"
        projectId={issue.project_id}
        disabled={disabled}
        workItemId={issue.id}
      />
    </div>
  );
});
