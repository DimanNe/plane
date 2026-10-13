/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef } from "react";
import { monitorForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { reaction, toJS } from "mobx";
// plane imports
import { getLinesGoneToAnotherGroup } from "@plane/blocks/list-group-change";
import type { TGroupedIssues } from "@plane/types";
// components
import { pointOutLineInNewGroup } from "@/components/issues/issue-layouts/list/new-work-item-arrival";

/**
 * A line of the List layout that leaves its group for another is pointed out: the state of a work item was set in
 * a list grouped by state, its priority in one grouped by priority, and so on. The groups are compared as the
 * store changes them, which is before the list draws the change: the line is then still at its old place.
 */
export const useListLineGroupChange = (groupedIssueIds: TGroupedIssues) => {
  // a line that the user drags to another group is where he has put it himself
  const isLineDraggedRef = useRef(false);
  useEffect(
    () =>
      monitorForElements({
        onDragStart: () => {
          isLineDraggedRef.current = true;
        },
        onDrop: () => {
          isLineDraggedRef.current = false;
        },
      }),
    []
  );

  useEffect(
    () =>
      reaction(
        () => toJS(groupedIssueIds),
        (groupedIssueIdsNow, groupedIssueIdsBefore) => {
          if (isLineDraggedRef.current) return;
          for (const line of getLinesGoneToAnotherGroup(groupedIssueIdsBefore, groupedIssueIdsNow))
            void pointOutLineInNewGroup(line.issueId, line.groupId, line.newGroupId);
        }
      ),
    [groupedIssueIds]
  );
};
