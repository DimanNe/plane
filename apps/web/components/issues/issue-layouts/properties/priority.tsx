/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { SyntheticEvent } from "react";
import { observer } from "mobx-react";
// plane imports
import type { TIssue } from "@plane/types";
// components
import { PrioritySelect } from "@/components/dropdowns/priority/priority-select";

type TIssuePropertyPriority = {
  issue: TIssue;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
  isReadOnly: boolean;
};

const handleEventPropagation = (e: SyntheticEvent<HTMLDivElement>) => {
  e.stopPropagation();
  e.preventDefault();
};

/**
 * The priority of a work item as its icon alone, for a list row; a click opens the priority menu.
 * The row itself is a link, so the click must not reach it.
 */
export const IssuePropertyPriority = observer(function IssuePropertyPriority(props: TIssuePropertyPriority) {
  const { issue, updateIssue, isReadOnly } = props;

  return (
    // oxlint-disable-next-line jsx_a11y/click-events-have-key-events oxlint-disable-next-line jsx_a11y/no-static-element-interactions
    <div className="mr-0.5 flex flex-shrink-0" onFocus={handleEventPropagation} onClick={handleEventPropagation}>
      <PrioritySelect
        value={issue.priority}
        onChange={(priority) => updateIssue?.(issue.project_id, issue.id, { priority })}
        disabled={isReadOnly}
        variant="icon-sm"
        className="focus-visible:ring-inset [&_svg]:size-4"
        tooltip
      />
    </div>
  );
});
