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
import { StateSelect } from "@/components/dropdowns/state/state-select";
import { filterValueProps } from "@/components/issues/issue-layouts/quick-action-dropdowns/filter-menu-helper";
import type { useStateMenuOfKey } from "@/components/power-k/hooks/use-state-menu-of-key";
// hooks
import { useListView } from "@/hooks/store/use-list-view";

type TIssuePropertyState = {
  issue: TIssue;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
  isReadOnly: boolean;
  stateMenuOfKey: ReturnType<typeof useStateMenuOfKey>;
};

const handleEventPropagation = (e: SyntheticEvent<HTMLDivElement>) => {
  e.stopPropagation();
  e.preventDefault();
};

/**
 * The state of a work item as its circle alone, for a list row; a click opens the state menu. The
 * row itself is a link, so the click must not reach it.
 */
export const IssuePropertyState = observer(function IssuePropertyState(props: TIssuePropertyState) {
  const { issue, updateIssue, isReadOnly, stateMenuOfKey } = props;
  // store hooks
  const { leaveSelectionAtPlaceOf } = useListView();

  return (
    // oxlint-disable-next-line jsx_a11y/click-events-have-key-events oxlint-disable-next-line jsx_a11y/no-static-element-interactions
    <div
      className="mr-0.5 flex flex-shrink-0"
      {...filterValueProps("state_id", issue.state_id)}
      onFocus={handleEventPropagation}
      onClick={handleEventPropagation}
    >
      <StateSelect
        value={issue.state_id}
        onChange={(stateId) => {
          const change = updateIssue?.(issue.project_id, issue.id, { state_id: stateId });
          // chosen by hand in the menu that the key S opened: as chosen there by its letter
          if (change && stateMenuOfKey.open) leaveSelectionAtPlaceOf(issue.id, change);
        }}
        projectId={issue.project_id ?? undefined}
        disabled={isReadOnly}
        variant="icon-sm"
        className="focus-visible:ring-inset"
        tooltip
        {...stateMenuOfKey}
      />
    </div>
  );
});
