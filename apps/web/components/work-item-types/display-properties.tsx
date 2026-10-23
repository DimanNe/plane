/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import type { IIssueDisplayProperties } from "@plane/types";
import { getWorkItemPropertyKey, isWorkItemPropertyDisplayProperty } from "@plane/utils";
// components
import { getDisplayPropertyToggleClassName } from "@/components/issues/issue-layouts/filters/header/display-filters/display-property-toggle";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";

type Props = {
  displayProperties: IIssueDisplayProperties;
  handleUpdate: (updatedDisplayProperties: Partial<IIssueDisplayProperties>) => void;
};

/** The toggles of the project's custom properties in the display properties of a layout. */
export const WorkItemPropertyDisplayProperties = observer(function WorkItemPropertyDisplayProperties(props: Props) {
  const { displayProperties, handleUpdate } = props;
  // router
  const { projectId } = useParams();
  // store hooks
  const { getProjectWorkItemProperties } = useWorkItemTypes();

  return (
    <>
      {getProjectWorkItemProperties(projectId?.toString())
        .filter(isWorkItemPropertyDisplayProperty)
        .map((property) => {
          const key = getWorkItemPropertyKey(property.id);
          return (
            <button
              key={property.id}
              type="button"
              className={getDisplayPropertyToggleClassName(!!displayProperties?.[key])}
              onClick={() => handleUpdate({ [key]: !displayProperties?.[key] })}
            >
              {property.display_name}
            </button>
          );
        })}
    </>
  );
});
