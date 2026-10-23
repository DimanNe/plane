/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MutableRefObject } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
// plane imports
import { DRAG_ALLOWED_GROUPS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
import type {
  IGroupByColumn,
  TIssueMap,
  TIssueGroupByOptions,
  TIssueOrderByOptions,
  TIssue,
  IIssueDisplayProperties,
  IPragmaticDropPayload,
  TIssueKanbanFilters,
} from "@plane/types";
import { EIssueLayoutTypes } from "@plane/types";
import { Row } from "@plane/blocks/layout";
import { cn } from "@plane/utils";
// components
import { ListLoaderItemRow } from "@/components/ui/loader/layouts/list-layout-loader";
import { useWorkFlowFDragNDrop } from "@/components/workflow";
// hooks
import { useCommandPalette } from "@/hooks/store/use-command-palette";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useIntersectionObserver } from "@/hooks/use-intersection-observer";
import { useListView } from "@/hooks/store/use-list-view";
import { useIssuesStore } from "@/hooks/use-issue-layout-store";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";
// local imports
import { GroupDragOverlay } from "../group-drag-overlay";
import { QuickAddIssueRoot } from "../quick-add";
import type { GroupDropLocation } from "../utils";
import { getIssueBlockId, getSourceFromDropPayload, highlightIssueOnDrop } from "../utils";
import { IssueBlocksList } from "./blocks-list";
import { ListDropLine } from "./drop-line";
import { HeaderGroupByCard } from "./headers/group-by-card";
import { ListGroupNewWorkItemButton } from "./headers/new-work-item-button";
import { getListGroupHeaderId, highlightNewWorkItem } from "./new-work-item-arrival";
import type { TRenderQuickActions } from "./list-view-types";
import { getCarriedSubIssueIds, getListDropLocation, getListDropMark } from "./utils";
import { getWorkItemDataOfGroup } from "./work-item-data-of-group";

interface Props {
  groupIssueIds: string[] | undefined;
  // the work items of all the groups of the list
  issueIdsOfList: Set<string>;
  group: IGroupByColumn;
  issuesMap: TIssueMap;
  group_by: TIssueGroupByOptions | null;
  orderBy: TIssueOrderByOptions | undefined;
  getGroupIndex: (groupId: string | undefined) => number;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
  quickActions: TRenderQuickActions;
  displayProperties: IIssueDisplayProperties | undefined;
  enableIssueQuickAdd: boolean;
  canEditProperties: (projectId: string | undefined) => boolean;
  containerRef: MutableRefObject<HTMLDivElement | null>;
  quickAddCallback?: ((projectId: string | null | undefined, data: TIssue) => Promise<TIssue | undefined>) | undefined;
  handleOnDrop: (source: GroupDropLocation, destination: GroupDropLocation) => Promise<void>;
  disableIssueCreation?: boolean;
  isCompletedCycle?: boolean;
  showEmptyGroup?: boolean;
  loadMoreIssues: (groupId?: string) => void;
  selectionHelpers: TSelectionHelper;
  handleCollapsedGroups: (value: string) => void;
  collapsedGroups: TIssueKanbanFilters;
  isEpic?: boolean;
}

export const ListGroup = observer(function ListGroup(props: Props) {
  const {
    groupIssueIds = [],
    issueIdsOfList,
    group,
    issuesMap,
    group_by,
    orderBy,
    getGroupIndex,
    updateIssue,
    quickActions,
    displayProperties,
    enableIssueQuickAdd,
    canEditProperties,
    containerRef,
    quickAddCallback,
    handleOnDrop,
    disableIssueCreation,
    isCompletedCycle,
    showEmptyGroup,
    loadMoreIssues,
    selectionHelpers,
    handleCollapsedGroups,
    collapsedGroups,
    isEpic = false,
  } = props;

  const [isDraggingOverColumn, setIsDraggingOverColumn] = useState(false);
  const [dragColumnOrientation, setDragColumnOrientation] = useState<"justify-start" | "justify-end">("justify-start");
  const [isQuickAddOpen, setIsQuickAddOpen] = useState(false);
  // a header at the lower edge of the list would open the input below that edge
  const showQuickAdd = useCallback(
    (element: HTMLDivElement | null) => element?.scrollIntoView({ block: "nearest" }),
    []
  );
  const isExpanded = !collapsedGroups?.group_by.includes(group.id);
  const groupRef = useRef<HTMLDivElement | null>(null);
  const { t } = useTranslation();
  const projectState = useProjectState();
  const { getGroupDropPlace, setDropMark, setGroupIdOfNewWorkItem } = useListView();
  const { toggleCreateIssueModal } = useCommandPalette();

  const {
    issues: { getGroupIssueCount, getPaginationData, getIssueLoader, getIssueIds },
  } = useIssuesStore();

  const [intersectionElement, setIntersectionElement] = useState<HTMLDivElement | null>(null);

  const { workflowDisabledSource, isWorkflowDropDisabled, handleWorkFlowState, getIsWorkflowWorkItemCreationDisabled } =
    useWorkFlowFDragNDrop(group_by);
  const isWorkflowIssueCreationDisabled = getIsWorkflowWorkItemCreationDisabled(group.id);

  const groupIssueCount = getGroupIssueCount(group.id, undefined, false) ?? 0;
  const nextPageResults = getPaginationData(group.id, undefined)?.nextPageResults;
  const isPaginating = !!getIssueLoader(group.id);

  useIntersectionObserver(containerRef, isPaginating ? null : intersectionElement, loadMoreIssues, `100% 0% 100% 0%`);

  const shouldLoadMore =
    nextPageResults === undefined && groupIssueCount !== undefined && groupIssueIds
      ? groupIssueIds.length < groupIssueCount
      : !!nextPageResults;

  const loadMore = isPaginating ? (
    <ListLoaderItemRow />
  ) : (
    // oxlint-disable-next-line jsx_a11y/click-events-have-key-events oxlint-disable-next-line jsx_a11y/no-static-element-interactions
    <div
      className={
        "relative flex h-11 cursor-pointer items-center gap-3 border border-transparent border-t-subtle-1 bg-surface-1 p-3 pl-8 text-13 font-medium text-accent-primary hover:text-accent-secondary hover:underline"
      }
      onClick={() => loadMoreIssues(group.id)}
    >
      {t("common.load_more")} &darr;
    </div>
  );

  const validateEmptyIssueGroups = (issueCount: number = 0) => {
    if (!showEmptyGroup && issueCount <= 0) return false;
    return true;
  };

  const prePopulateQuickAddData = (groupByKey: string | null, value: any) =>
    getWorkItemDataOfGroup(groupByKey, value, projectState.projectStates?.find((state) => state.default)?.id);

  useEffect(() => {
    const element = groupRef.current;

    if (!element) return;

    // for a group that takes no drop nothing is marked: the cover over its rows says why
    const markDropPlace = (payload: IPragmaticDropPayload) =>
      setDropMark(
        isWorkflowDropDisabled || group.isDropDisabled
          ? undefined
          : getListDropMark(payload, getIssueIds(group.id) ?? [], issuesMap, issueIdsOfList, orderBy === "sort_order")
      );

    return combine(
      dropTargetForElements({
        element,
        getData: () => ({ groupId: group.id, type: "COLUMN" }),
        onDragEnter: (payload) => {
          setIsDraggingOverColumn(true);
          markDropPlace(payload);
        },
        onDragLeave: () => {
          setIsDraggingOverColumn(false);
          setDropMark(undefined);
        },
        onDragStart: () => {
          setIsDraggingOverColumn(true);
        },
        onDrag: (payload) => {
          const { source } = payload;
          markDropPlace(payload);
          const sourceGroupId = source?.data?.groupId as string | undefined;
          const currentGroupId = group.id;

          // oxlint-disable-next-line no-unused-expressions
          sourceGroupId && handleWorkFlowState(sourceGroupId, currentGroupId);

          const sourceIndex = getGroupIndex(sourceGroupId);
          const currentIndex = getGroupIndex(currentGroupId);

          if (sourceIndex > currentIndex) {
            setDragColumnOrientation("justify-end");
          } else {
            setDragColumnOrientation("justify-start");
          }
        },
        onDrop: (payload) => {
          setIsDraggingOverColumn(false);
          setDropMark(undefined);
          const source = getSourceFromDropPayload(payload);
          const destination = getListDropLocation(payload, getIssueIds(group.id) ?? [], issuesMap, issueIdsOfList);

          if (!source || !destination) return;

          if (isWorkflowDropDisabled || group.isDropDisabled) {
            if (group.dropErrorMessage)
              setToast({
                type: "warning",
                title: t("common.warning"),
                message: group.dropErrorMessage,
              });
            return;
          }

          handleOnDrop(
            {
              ...source,
              carriedSubIssueIds: source.id
                ? getCarriedSubIssueIds(source.id, getIssueIds(source.groupId) ?? [], issuesMap, issueIdsOfList)
                : undefined,
            },
            destination
          );

          highlightIssueOnDrop(getIssueBlockId(source.id, destination?.groupId), orderBy !== "sort_order");

          if (!isExpanded) {
            handleCollapsedGroups(group.id);
          }
        },
      })
    );
  }, [
    // oxlint-disable-next-line eslint-plugin-react-hooks/exhaustive-deps
    groupRef?.current,
    group,
    orderBy,
    getGroupIndex,
    setDragColumnOrientation,
    setIsDraggingOverColumn,
    isWorkflowDropDisabled,
    issueIdsOfList,
  ]);

  const isDragAllowed = group_by ? DRAG_ALLOWED_GROUPS.includes(group_by) : true;
  const canOverlayBeVisible = isWorkflowDropDisabled || !!group.isDropDisabled;
  const isDropDisabled = isWorkflowDropDisabled || !!group.isDropDisabled;

  const isGroupByCreatedBy = group_by === "created_by";
  const shouldExpand = (!!groupIssueCount && isExpanded) || !group_by;
  const dropPlace = getGroupDropPlace(group.id);
  const isQuickAddAllowed =
    enableIssueQuickAdd &&
    !disableIssueCreation &&
    !isGroupByCreatedBy &&
    !isCompletedCycle &&
    !isWorkflowIssueCreationDisabled;

  return validateEmptyIssueGroups(groupIssueCount) ? (
    <div
      ref={groupRef}
      className={cn(`relative flex flex-shrink-0 flex-col`, {
        "border-accent-strong": isDraggingOverColumn,
        "border-danger-subtle": isDraggingOverColumn && isDropDisabled,
      })}
    >
      {/* The header and the input under it stay at the top of the list together while their group scrolls. */}
      <div className={cn("w-full flex-shrink-0", { "sticky top-0 z-[2]": isExpanded && groupIssueCount > 0 })}>
        <Row
          id={getListGroupHeaderId(group.id)}
          className={cn("border-b border-subtle bg-layer-1 py-1 pr-3 hover:bg-layer-1-hover", {
            "bg-accent-subtle outline-2 -outline-offset-2 outline-accent-strong hover:bg-accent-subtle": !!dropPlace,
          })}
        >
          <HeaderGroupByCard
            groupID={group.id}
            groupBy={group_by}
            icon={group.icon}
            title={group.name}
            count={groupIssueCount}
            canEditProperties={canEditProperties}
            selectionHelpers={selectionHelpers}
            handleCollapsedGroups={handleCollapsedGroups}
            newWorkItemButton={
              isQuickAddAllowed && (
                <ListGroupNewWorkItemButton
                  isEpic={isEpic}
                  onClick={() => {
                    if (!isExpanded) handleCollapsedGroups(group.id);
                    // FOR_REVIEWER: an epic keeps the inline input, since the dialog of N I makes a work item;
                    // no list of this edition shows epics.
                    if (isEpic) return setIsQuickAddOpen(true);
                    // the dialog of N I, so that a description can be given too
                    setGroupIdOfNewWorkItem(group.id);
                    toggleCreateIssueModal(true);
                  }}
                />
              )
            }
          />
        </Row>
        {isQuickAddAllowed && isQuickAddOpen && (
          <div ref={showQuickAdd}>
            <QuickAddIssueRoot
              isQuickAddOpen
              setIsQuickAddOpen={setIsQuickAddOpen}
              layout={EIssueLayoutTypes.LIST}
              prePopulatedData={prePopulateQuickAddData(group_by, group.id)}
              containerClassName="border-b border-subtle bg-surface-1"
              quickAddCallback={
                quickAddCallback &&
                (async (projectId, data) => {
                  const workItem = await quickAddCallback(projectId, data);
                  if (workItem) highlightNewWorkItem(workItem.id);
                  return workItem;
                })
              }
              isEpic={isEpic}
            />
          </div>
        )}
      </div>
      {shouldExpand && (
        <div className="relative">
          <GroupDragOverlay
            dragColumnOrientation={dragColumnOrientation}
            canOverlayBeVisible={canOverlayBeVisible}
            isDropDisabled={isDropDisabled}
            workflowDisabledSource={workflowDisabledSource}
            dropErrorMessage={group.dropErrorMessage}
            orderBy={orderBy}
            isDraggingOverColumn={isDraggingOverColumn}
            isEpic={isEpic}
          />
          {groupIssueIds && (
            <IssueBlocksList
              issueIds={groupIssueIds}
              issueIdsOfList={issueIdsOfList}
              groupId={group.id}
              issuesMap={issuesMap}
              updateIssue={updateIssue}
              quickActions={quickActions}
              displayProperties={displayProperties}
              canEditProperties={canEditProperties}
              containerRef={containerRef}
              isDragAllowed={isDragAllowed}
              canDropOverIssue={!canOverlayBeVisible}
              selectionHelpers={selectionHelpers}
              isEpic={isEpic}
            />
          )}
          {dropPlace === "end" && <ListDropLine />}

          {shouldLoadMore &&
            (group_by ? (
              <>{loadMore}</>
            ) : (
              <>
                {Array.from({ length: 2 }).map((_, index) => (
                  // oxlint-disable-next-line react/no-array-index-key
                  <ListLoaderItemRow key={index} />
                ))}
                <ListLoaderItemRow ref={setIntersectionElement} />
              </>
            ))}
        </div>
      )}
    </div>
  ) : null;
});
