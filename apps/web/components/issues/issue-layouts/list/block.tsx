/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MouseEvent } from "react";
import { useEffect, useRef } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { ChevronRightOutline } from "@makeplane/propel/icons";
// types
import { setToast } from "@plane/blocks/toast";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import type { TIssue, IIssueDisplayProperties, TIssueMap } from "@plane/types";
import { EIssueServiceType } from "@plane/types";
// ui
import { ControlLink, Row } from "@plane/blocks/layout";
import { Spinner } from "@plane/blocks/spinner";
import { cn, generateWorkItemLink, getTextFromHTML } from "@plane/utils";
// components
import { MultipleSelectEntityAction } from "@/components/core/multiple-select";
import { IssueProperties } from "@/components/issues/issue-layouts/properties";
import { IssuePropertyState } from "@/components/issues/issue-layouts/properties/state";
import { IssueIdentifier } from "@/components/issues/issue-detail/issue-identifier";
// hooks
import { useAppTheme } from "@/hooks/store/use-app-theme";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";
import { useProject } from "@/hooks/store/use-project";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";
import { usePlatformOS } from "@/hooks/use-platform-os";
import { calculateIdentifierWidth } from "../utils";
import { IssueBlockAddSubIssue } from "./block-add-sub-issue";
import { IssueBlockTitle } from "./block-title";
import type { TRenderQuickActions } from "./list-view-types";

interface IssueBlockProps {
  issueId: string;
  issuesMap: TIssueMap;
  groupId: string;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
  quickActions: TRenderQuickActions;
  displayProperties: IIssueDisplayProperties | undefined;
  canEditProperties: (projectId: string | undefined) => boolean;
  nestingLevel: number;
  spacingLeft?: number;
  hasSubIssues: boolean;
  isExpanded: boolean;
  selectionHelpers: TSelectionHelper;
  isCurrentBlockDragging: boolean;
  setIsCurrentBlockDragging: React.Dispatch<React.SetStateAction<boolean>>;
  canDrag: boolean;
  isCompact: boolean;
  isEpic?: boolean;
}

export const IssueBlock = observer(function IssueBlock(props: IssueBlockProps) {
  const {
    issuesMap,
    issueId,
    groupId,
    updateIssue,
    quickActions,
    displayProperties,
    canEditProperties,
    nestingLevel,
    spacingLeft = 14,
    hasSubIssues,
    isExpanded,
    selectionHelpers,
    isCurrentBlockDragging,
    setIsCurrentBlockDragging,
    canDrag,
    isCompact,
    isEpic = false,
  } = props;
  // ref
  const issueRef = useRef<HTMLDivElement | null>(null);
  const isPeekOpenOnPressRef = useRef(false);
  // router
  const { workspaceSlug: routerWorkspaceSlug, projectId: routerProjectId } = useParams();
  const workspaceSlug = routerWorkspaceSlug?.toString();
  const projectId = routerProjectId?.toString();
  // hooks
  const { sidebarCollapsed: isSidebarCollapsed } = useAppTheme();
  const { getProjectIdentifierById, currentProjectNextSequenceId } = useProject();
  const { getIsIssuePeeked, peekIssue, setPeekIssue } = useIssueDetail(
    isEpic ? EIssueServiceType.EPICS : EIssueServiceType.ISSUES
  );
  const { getIsRowSelected, getIsRowTitleEdited, setSelectedRow, toggleIssueCollapse } = useListView();

  const handleIssuePeekOverview = (issue: TIssue) =>
    workspaceSlug &&
    issue &&
    issue.project_id &&
    issue.id &&
    !getIsIssuePeeked(issue.id) &&
    setPeekIssue({
      workspaceSlug,
      projectId: issue.project_id,
      issueId: issue.id,
      nestingLevel: nestingLevel,
      isArchived: !!issue.archived_at,
    });

  // derived values
  const issue = issuesMap[issueId];
  const canEditIssueProperties = canEditProperties(issue?.project_id ?? undefined);
  const isDraggingAllowed = canDrag && canEditIssueProperties;
  const isTitleEdited = getIsRowTitleEdited(issueId, groupId);

  const { isMobile } = usePlatformOS();

  useEffect(() => {
    const element = issueRef.current;

    if (!element) return;

    return combine(
      draggable({
        element,
        canDrag: () => isDraggingAllowed && !isTitleEdited,
        getInitialData: () => ({ id: issueId, type: "ISSUE", groupId }),
        onDragStart: () => {
          setIsCurrentBlockDragging(true);
        },
        onDrop: () => {
          setIsCurrentBlockDragging(false);
        },
      })
    );
  }, [isDraggingAllowed, isTitleEdited, issueId, groupId, setIsCurrentBlockDragging]);

  if (!issue) return null;

  const projectIdentifier = getProjectIdentifierById(issue.project_id);
  const isIssueSelected = selectionHelpers.getIsEntitySelected(issue.id);
  const isIssueActive = selectionHelpers.getIsEntityActive(issue.id);
  const isRowSelected = getIsRowSelected(issue.id, groupId);
  const isSubIssue = nestingLevel !== 0;
  const canSelectIssues = canEditIssueProperties && !selectionHelpers.isSelectionDisabled;

  const marginLeft = `${spacingLeft}px`;

  const handleToggleExpand = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    e.preventDefault();
    toggleIssueCollapse(issue.id);
  };

  // Calculate width for: projectIdentifier + "-" + dynamic sequence number digits
  // Use next_work_item_sequence from backend (static value from project endpoint)
  const maxSequenceId = currentProjectNextSequenceId ?? 1;
  const keyMinWidth = displayProperties?.key
    ? calculateIdentifierWidth(projectIdentifier?.length ?? 0, maxSequenceId)
    : 0;

  const workItemLink = generateWorkItemLink({
    workspaceSlug,
    projectId: issue?.project_id,
    issueId,
    projectIdentifier,
    sequenceId: issue?.sequence_id,
    isEpic,
    isArchived: !!issue?.archived_at,
  });
  return (
    <ControlLink
      id={`issue-${issue.id}`}
      href={workItemLink}
      // the work item view beside the list closes on a press outside it, before the click arrives
      onMouseDown={() => {
        isPeekOpenOnPressRef.current = !!peekIssue;
      }}
      onClick={(e) => {
        // a click selects the row; a double click, or Enter on the row, opens it and ends the editing of its title
        const isOpening = e.detail !== 1;
        if (isOpening || !getIsRowSelected(issue.id, groupId)) setSelectedRow({ issueId: issue.id, groupId });
        // the work item view beside the list follows the selection while it is open
        if (isOpening || isPeekOpenOnPressRef.current) handleIssuePeekOverview(issue);
      }}
      className={cn("w-full cursor-pointer", { "outline-none": isRowSelected })}
      disabled={!!issue?.tempId || issue?.is_draft}
    >
      <Row
        ref={issueRef}
        className={cn(
          "group/list-block relative flex min-h-11 flex-col gap-3 bg-layer-transparent py-3 text-13 transition-colors hover:bg-layer-transparent-hover",
          {
            "min-h-9 py-2": isCompact,
            "bg-layer-transparent-selected hover:bg-layer-transparent-selected": isRowSelected,
            "border-accent-strong": getIsIssuePeeked(issue.id) && peekIssue?.nestingLevel === nestingLevel,
            "border-strong-1": isIssueActive,
            "last:border-b-transparent": !getIsIssuePeeked(issue.id) && !isIssueActive,
            "bg-accent-primary/5 hover:bg-accent-primary/10": isIssueSelected,
            "bg-layer-1": isCurrentBlockDragging,
            "md:flex-row md:items-center": isSidebarCollapsed,
            "lg:flex-row lg:items-center": !isSidebarCollapsed,
          }
        )}
        onDragStart={() => {
          if (!isDraggingAllowed) {
            setToast({
              type: "warning",
              title: "Cannot move work item",
              message: !canEditIssueProperties
                ? "You are not allowed to move this work item"
                : "Drag and drop is disabled for the current grouping",
            });
          }
        }}
      >
        <div className="flex w-full gap-2 truncate">
          <div className="flex flex-grow items-center gap-0.5 truncate">
            <div className="flex items-center gap-1" style={isSubIssue ? { marginLeft } : {}}>
              {/* select checkbox */}
              {projectId && canSelectIssues && !isEpic && (
                <Tooltip
                  label="Only work items within the current project can be selected."
                  layout="stacked"
                  disabled={issue.project_id === projectId}
                >
                  <div className="absolute left-1 grid w-3.5 flex-shrink-0 place-items-center">
                    <MultipleSelectEntityAction
                      className={cn(
                        "pointer-events-none opacity-0 transition-opacity group-hover/list-block:pointer-events-auto group-hover/list-block:opacity-100",
                        {
                          "pointer-events-auto opacity-100": isIssueSelected,
                        }
                      )}
                      groupId={groupId}
                      id={issue.id}
                      selectionHelpers={selectionHelpers}
                      disabled={issue.project_id !== projectId}
                    />
                  </div>
                </Tooltip>
              )}
              {displayProperties && (displayProperties.key || displayProperties.issue_type) && (
                <div className="flex-shrink-0" style={{ minWidth: `${keyMinWidth}px` }}>
                  {issue.project_id && (
                    <IssueIdentifier
                      issueId={issueId}
                      projectId={issue.project_id}
                      size="xs"
                      variant="tertiary"
                      displayProperties={displayProperties}
                    />
                  )}
                </div>
              )}

              {/* sub-issues chevron */}
              <div className="grid size-4 flex-shrink-0 place-items-center">
                {hasSubIssues && !isEpic && (
                  <button
                    type="button"
                    className="grid size-4 place-items-center rounded-xs text-placeholder hover:text-tertiary"
                    onClick={handleToggleExpand}
                  >
                    <ChevronRightOutline
                      className={cn("size-4", {
                        "rotate-90": isExpanded,
                      })}
                    />
                  </button>
                )}
              </div>

              {issue?.tempId !== undefined && (
                <div className="absolute top-0 left-0 z-[99999] h-full w-full animate-pulse bg-surface-1/20" />
              )}
            </div>

            <IssuePropertyState issue={issue} updateIssue={updateIssue} isReadOnly={!canEditIssueProperties} />
            <IssueBlockTitle
              issue={issue}
              groupId={groupId}
              nestingLevel={nestingLevel}
              isEditingAllowed={canEditIssueProperties}
              isTooltipDisabled={isCurrentBlockDragging || isMobile}
              updateIssue={updateIssue}
            />
            {!isTitleEdited && (
              // What follows the title shares one cell, so the chip lies over the start of the description. The
              // cell takes the room the title leaves; the description goes when that is too little for it.
              <div className="ml-1.5 grid min-w-0 flex-1 items-center *:col-start-1 *:row-start-1 *:min-w-0">
                {displayProperties?.description && issue.description_prefix && (
                  <div className="@container">
                    <p
                      className={cn(
                        "hidden truncate text-secondary @min-[7rem]:block",
                        ["text-body-xs-regular", "text-caption-md-regular", "text-caption-sm-regular"][
                          Math.min(nestingLevel, 2)
                        ]
                      )}
                    >
                      {getTextFromHTML(issue.description_prefix)}
                    </p>
                  </div>
                )}
                {canEditIssueProperties && <IssueBlockAddSubIssue issueId={issue.id} />}
              </div>
            )}
          </div>
          {!issue?.tempId && (
            <div
              className={cn("block rounded-sm border border-strong", {
                "md:hidden": isSidebarCollapsed,
                "lg:hidden": !isSidebarCollapsed,
              })}
            >
              {quickActions({
                issue,
                parentRef: issueRef,
              })}
            </div>
          )}
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          {!issue?.tempId ? (
            <>
              <IssueProperties
                className={`relative flex flex-wrap ${isSidebarCollapsed ? "md:flex-shrink-0 md:flex-grow" : "lg:flex-shrink-0 lg:flex-grow"} items-center gap-2 whitespace-nowrap`}
                issue={issue}
                isReadOnly={!canEditIssueProperties}
                updateIssue={updateIssue}
                displayProperties={displayProperties}
                activeLayout="List"
                isEpic={isEpic}
              />
              {/* oxlint-disable-next-line jsx_a11y/click-events-have-key-events oxlint-disable-next-line jsx_a11y/no-static-element-interactions */}
              <div
                className={cn("hidden", {
                  "md:flex": isSidebarCollapsed,
                  "lg:flex": !isSidebarCollapsed,
                })}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
              >
                {quickActions({
                  issue,
                  parentRef: issueRef,
                })}
              </div>
            </>
          ) : (
            <div className="h-4 w-4">
              <Spinner className="h-4 w-4" />
            </div>
          )}
        </div>
      </Row>
    </ControlLink>
  );
});
