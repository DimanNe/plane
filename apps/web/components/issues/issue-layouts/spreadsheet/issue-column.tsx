/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
import { observer } from "mobx-react";
// types
import type { IIssueDisplayProperties, TIssue } from "@plane/types";
import { isWorkItemPropertyKey } from "@plane/utils";
// constants
import { SPREADSHEET_COLUMNS } from "../utils";
// components
import { SpreadsheetWorkItemPropertyColumn } from "@/components/work-item-types/property-column";
import { shouldRenderColumn } from "@/helpers/issue-filter.helper";
import { WithDisplayPropertiesHOC } from "../properties/with-display-properties-HOC";

type Props = {
  displayProperties: IIssueDisplayProperties;
  issueDetail: TIssue;
  disableUserActions: boolean;
  property: keyof IIssueDisplayProperties;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
  isEstimateEnabled: boolean;
};

export const IssueColumn = observer(function IssueColumn(props: Props) {
  const { displayProperties, issueDetail, disableUserActions, property, updateIssue } = props;
  // router
  const tableCellRef = useRef<HTMLTableCellElement | null>(null);

  const shouldRenderProperty = shouldRenderColumn(property);

  // every custom property has a column of its own, all drawn by one component
  const Column =
    SPREADSHEET_COLUMNS[property] ?? (isWorkItemPropertyKey(property) ? SpreadsheetWorkItemPropertyColumn : undefined);

  if (!Column) return null;

  const handleUpdateIssue = async (issue: TIssue, data: Partial<TIssue>) => {
    if (updateIssue) await updateIssue(issue.project_id, issue.id, data);
  };

  return (
    <WithDisplayPropertiesHOC
      displayProperties={displayProperties}
      displayPropertyKey={property}
      shouldRenderProperty={() => shouldRenderProperty}
    >
      <td
        tabIndex={0}
        className="h-11 min-w-36 border-r-[1px] border-subtle text-13 after:absolute after:bottom-[-1px] after:w-full after:border after:border-subtle"
        ref={tableCellRef}
      >
        <Column
          issue={issueDetail}
          property={property}
          onChange={handleUpdateIssue}
          disabled={disableUserActions}
          onClose={() => tableCellRef?.current?.focus()}
        />
      </td>
    </WithDisplayPropertiesHOC>
  );
});
