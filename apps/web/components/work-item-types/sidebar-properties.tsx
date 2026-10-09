/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EWorkItemPropertyType } from "@plane/types";
import { getWorkItemPropertyTypeKey, isWorkItemPropertyValueRequired } from "@plane/utils";
// components
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import type { TIssueOperations } from "@/components/issues/issue-detail/root";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WORK_ITEM_PROPERTY_TYPE_ICONS } from "./property-icon";
import { WorkItemPropertyInput } from "./property-input";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  issueOperations: TIssueOperations;
  disabled: boolean;
};

/** The properties of the work item's type, for the property list of the detail page and of the peek view. */
export const WorkItemSidebarProperties = observer(function WorkItemSidebarProperties(props: Props) {
  const { workspaceSlug, projectId, issueId, issueOperations, disabled } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getWorkItemTypeProperties } = useWorkItemTypes();
  // derived values
  const issue = getIssueById(issueId);

  if (!issue) return null;

  const properties = getWorkItemTypeProperties(issue.type_id).filter((property) => property.is_active);
  const hasFormula = properties.some((property) => property.property_type === EWorkItemPropertyType.FORMULA);

  return (
    <>
      {properties.map((property) => {
        const isFormula = property.property_type === EWorkItemPropertyType.FORMULA;
        return (
          <SidebarPropertyListItem
            key={property.id}
            icon={WORK_ITEM_PROPERTY_TYPE_ICONS[getWorkItemPropertyTypeKey(property)]}
            label={property.display_name}
            appendElement={
              isWorkItemPropertyValueRequired(property) ? <span className="text-danger-primary">*</span> : undefined
            }
          >
            <WorkItemPropertyInput
              property={property}
              value={(isFormula ? issue.formula_values : issue.custom_properties)?.[property.id]}
              formulaError={issue.formula_errors?.[property.id]}
              onChange={async (value) => {
                await issueOperations.update(workspaceSlug, projectId, issueId, {
                  custom_properties: { [property.id]: value },
                });
                // the server computes formulas: the work item is read again to show what the new value gives
                if (hasFormula) await issueOperations.fetch(workspaceSlug, projectId, issueId);
              }}
              variant="select-ghost-md"
              projectId={projectId}
              disabled={disabled}
              workItemId={issueId}
            />
          </SidebarPropertyListItem>
        );
      })}
    </>
  );
});
