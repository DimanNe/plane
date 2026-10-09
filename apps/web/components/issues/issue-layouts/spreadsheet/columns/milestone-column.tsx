/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { TIssue } from "@plane/types";
// components
import { MilestoneSelect } from "@/components/milestones/select";

type Props = {
  issue: TIssue;
  onClose: () => void;
  onChange: (issue: TIssue, data: Partial<TIssue>, updates: any) => void;
  disabled: boolean;
};

export const SpreadsheetMilestoneColumn = observer(function SpreadsheetMilestoneColumn(props: Props) {
  const { issue, onChange, disabled, onClose } = props;
  // translation
  const { t } = useTranslation();

  return (
    <div className="h-11 border-b-[0.5px] border-subtle">
      <MilestoneSelect
        projectId={issue.project_id ?? undefined}
        value={issue.milestone_id}
        onChange={(data) =>
          onChange(issue, { milestone_id: data }, { changed_property: "milestone", change_details: data })
        }
        disabled={disabled}
        placeholder={t("project_milestones.no_milestone")}
        onClose={onClose}
        // `.clickable` is what the table's keyboard navigation clicks on Enter / Space in a focused cell.
        className="clickable"
        variant="table-cell"
      />
    </div>
  );
});
