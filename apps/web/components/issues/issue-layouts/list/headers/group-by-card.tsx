/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { CircleDashed } from "lucide-react";
// types
import type { TIssueGroupByOptions } from "@plane/types";
// components
import { cn } from "@plane/utils";
import { MultipleSelectGroupAction } from "@/components/core/multiple-select";
// constants
import type { TSelectionHelper } from "@/hooks/use-multiple-select";

interface IHeaderGroupByCard {
  groupID: string;
  groupBy: TIssueGroupByOptions;
  icon?: React.ReactNode;
  title: string;
  count: number;
  canEditProperties: (projectId: string | undefined) => boolean;
  selectionHelpers: TSelectionHelper;
  handleCollapsedGroups: (value: string) => void;
  newWorkItemButton?: React.ReactNode;
}

export const HeaderGroupByCard = observer(function HeaderGroupByCard(props: IHeaderGroupByCard) {
  const { groupID, icon, title, count, canEditProperties, selectionHelpers, handleCollapsedGroups, newWorkItemButton } =
    props;
  // router
  const { projectId } = useParams();
  // derived values
  const isGroupSelectionEmpty = selectionHelpers.isGroupSelected(groupID) === "empty";
  // auth
  const canSelectIssues = canEditProperties(projectId?.toString()) && !selectionHelpers.isSelectionDisabled;

  return (
    <>
      <div className="group/list-header flex w-full flex-shrink-0 items-center gap-2 py-1.5">
        {canSelectIssues && (
          <div className="absolute left-1 flex w-3.5 flex-shrink-0 items-center">
            <MultipleSelectGroupAction
              className={cn(
                "pointer-events-none size-3.5 opacity-0 !outline-none group-hover/list-header:pointer-events-auto group-hover/list-header:opacity-100",
                {
                  "pointer-events-auto opacity-100": !isGroupSelectionEmpty,
                }
              )}
              groupID={groupID}
              selectionHelpers={selectionHelpers}
              disabled={count === 0}
            />
          </div>
        )}
        <div className="grid flex-shrink-0 place-items-center overflow-hidden">
          {icon ?? <CircleDashed className="size-3.5" strokeWidth={2} />}
        </div>

        {/* eslint-disable-next-line jsx_a11y/click-events-have-key-events eslint-disable-next-line jsx_a11y/no-static-element-interactions */}
        <div
          className="relative flex w-full cursor-pointer flex-row items-center gap-1 overflow-hidden"
          onClick={() => handleCollapsedGroups(groupID)}
        >
          <div className="line-clamp-1 inline-block truncate font-medium text-primary">{title}</div>
          <div className="pl-2 text-13 font-medium text-tertiary">{count || 0}</div>
          {newWorkItemButton}
          <div className="px-2.5"></div>
        </div>
      </div>
    </>
  );
});
