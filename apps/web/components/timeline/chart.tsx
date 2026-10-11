/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { clamp, mapValues, once } from "lodash-es";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { createPortal } from "react-dom";
// plane imports
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { ArrowCollapseOutline, FullScreenOutline } from "@makeplane/propel/icons";
import { DropIndicator } from "@plane/blocks/common";
import { Row } from "@plane/blocks/layout";
import { getConflictCause, moveTask, removeTask, resizeTask } from "@plane/blocks/timeline-schedule";
import type { TPlan, TSchedule, TScheduleArrow, TTaskEdge } from "@plane/blocks/timeline-schedule";
import { ALL_ISSUES } from "@plane/constants";
import { useLatestCallback } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// components
import {
  BLOCK_HEIGHT,
  GANTT_BREADCRUMBS_HEIGHT,
  HEADER_HEIGHT,
  SIDEBAR_WIDTH,
} from "@/components/gantt-chart/constants";
import { MilestoneTimelineMarkers } from "@/components/milestones/timeline-markers";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";
import { useUserProfile } from "@/hooks/store/user";
import { useCurrentTime } from "@/hooks/use-current-time";
import { useIntersectionObserver } from "@/hooks/use-intersection-observer";
import useIssuePeekOverviewRedirection from "@/hooks/use-issue-peek-overview-redirection";
import { usePlatformOS } from "@/hooks/use-platform-os";
import useSize from "@/hooks/use-window-size";
// local imports
import { TimelineArrowControl } from "./arrow-control";
import { TimelineArrowTexts } from "./arrow-texts";
import { getDrawnArrows, TimelineArrowControls, TimelineArrows, TimelineDrawnArrow } from "./arrows";
import { TimelineBackdrop } from "./backdrop";
import { TimelineApartLink, TimelineConflict } from "./conflict";
import { TimelineBarDimension } from "./dimension";
import { TimelineHeader } from "./header";
import { TimelineDateMarkers } from "./markers";
import { TimelineDaysContext, TimelineLine } from "./line";
import { runOperation } from "./operation";
import type { TTimelineOperation } from "./operation";
import { trackPointer } from "./pointer";
import { getDateOfDay, getDayOfDate, getDayOfTime, getDayX, MIN_BAR_WIDTH, TimelineViewContext } from "./scale";
import type { THandle } from "./use-arrow-link";
import { useArrowLink } from "./use-arrow-link";
import { useDelayedHover } from "./use-delayed-hover";
import { useDeleteKey } from "./use-delete-key";
import { useEntryAnchor } from "./use-entry-anchor";
import { useTimelineView } from "./use-timeline-view";
import { useWheelTurn } from "./use-wheel-turn";

type Props = {
  // the tasks of the list, a line each, in the order of the list
  taskIds: string[];
  // the plan and its schedule: of what is stored, or of the operation that is going on
  plan: TPlan;
  schedule: TSchedule;
  operation: TTimelineOperation;
  // a day the timeline shows when it opens, besides its bars and today
  focusDate?: string | null;
  isEditable: boolean;
  showOnlyLeaves: boolean;
  onShowOnlyLeavesChange: (showOnlyLeaves: boolean) => void;
  // A line was dropped before the line that has `lineIndex` now, or after the last one. Not given where the
  // lines have no order that a move can change.
  onLineMove?: (taskId: string, lineIndex: number) => void;
  quickAdd?: ReactNode;
  loadMore?: () => void;
};

type TPosition = { clientX: number; clientY: number };

// lines drawn above and below the ones in view
const LINES_BEYOND_VIEW = 5;
// the widest and the narrowest day the timeline opens with
const MAX_INITIAL_PX_PER_DAY = 40;
const MIN_INITIAL_PX_PER_DAY = 2;
// the middle of a handle is this far outside its end of the bar
const HANDLE_DISTANCE = 9;
// What a conflict says shows a moment after the pointer came over its arrow, and goes a moment after it left.
const HOVER_DELAY = 150;
const LEAVE_DELAY = 300;
// The dates and the length of a bar show a moment after the pointer came over it: a little longer than a pointer
// that crosses bars on its way is over one of them.
const BAR_HOVER_DELAY = 200;
const NO_CAUSE: ReturnType<typeof getConflictCause> = { taskIds: [], arrowIds: [] };

/**
 * A copy of text of the timeline, also of what opens from it, carries plain text only. The browser would add the
 * selection as HTML with the styles of every element in it, many times the size of the text, and the program it
 * is pasted into may take that or wait for it.
 */
const copyAsPlainText = (copy: React.ClipboardEvent) => {
  const text = document.getSelection()?.toString();
  if (!text) return;
  copy.clipboardData.setData("text/plain", text);
  copy.preventDefault();
};

/**
 * The timeline of tasks: the list at the left, a line with a bar per task, the arrows between the bars. It draws
 * the plan it is given, and every gesture on it is an operation: begun at the first movement, shown at every
 * further one as the engine computes it, saved on release and dropped on Escape.
 */
export const TimelineChart = observer(function TimelineChart(props: Props) {
  const {
    taskIds,
    plan: { tasks, arrows },
    schedule,
    operation,
    focusDate,
    isEditable,
    showOnlyLeaves,
    onShowOnlyLeavesChange,
    onLineMove,
    quickAdd,
    loadMore,
  } = props;
  // router
  const { workspaceSlug } = useParams();
  // refs
  const isPeekOpenOnPressRef = useRef(false);
  // states
  // the element that scrolls the lines, and the one as wide as the timeline; full screen draws both anew
  const [scroll, setScroll] = useState<HTMLDivElement | null>(null);
  const [canvas, setCanvas] = useState<HTMLDivElement | null>(null);
  const [firstLineInView, setFirstLineInView] = useState(0);
  // The task that is dragged. When it is its line that moves: the line before which it would land, and how far
  // it is from its place, in pixels.
  const [drag, setDrag] = useState<{ taskId: string; lineIndex?: number; lineOffset?: number }>();
  // the arrow the pointer is over, and the task whose bar it is over
  const [hoveredArrowId, hoverArrow, setHoveredArrowId] = useDelayedHover<string>(HOVER_DELAY, LEAVE_DELAY);
  const [hoveredTaskId, handleBarHover] = useDelayedHover<string>(BAR_HOVER_DELAY, LEAVE_DELAY);
  // the selected arrow, whose control is open, with the place of the window where it was clicked
  const [selectedArrow, setSelectedArrow] = useState<{ id: string; point: { x: number; y: number } }>();
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [loadMoreElement, setLoadMoreElement] = useState<HTMLDivElement | null>(null);
  // store hooks
  const { data: userProfile } = useUserProfile();
  const {
    issue: { getIssueById },
    peekIssue,
  } = useIssueDetail();
  const listView = useListView();
  const { setSelectedRow } = listView;
  // hooks
  const { t } = useTranslation();
  const { isMobile } = usePlatformOS();
  const { handleRedirection } = useIssuePeekOverviewRedirection();
  const { currentTime } = useCurrentTime();
  const [, windowHeight] = useSize();
  // derived values
  const days = useMemo(
    () => mapValues(schedule.dates, ({ start, end }) => ({ start: getDayOfDate(start), end: getDayOfDate(end) })),
    [schedule.dates]
  );
  const lineIndexes = useMemo(() => new Map(taskIds.map((taskId, index) => [taskId, index])), [taskIds]);
  const followingTaskIds = useMemo(
    () => new Set(tasks.flatMap((task) => (task.start === "anchor" ? [task.id] : []))),
    [tasks]
  );
  const now = getDayOfTime(currentTime);
  const startOfWeek = userProfile.start_of_the_week;

  // all the bars and today, as long as that leaves a day wide enough; else what is around today
  const getInitialView = (width: number) => {
    const focusDay = focusDate ? getDayOfDate(focusDate) : now;
    const shownDays = [focusDay, ...Object.values(days).flatMap(({ start, end }) => [start, end + 1])];
    const from = Math.min(now, ...shownDays);
    const to = Math.max(now, ...shownDays);
    const pxPerDay = clamp((0.9 * width) / (to - from), MIN_INITIAL_PX_PER_DAY, MAX_INITIAL_PX_PER_DAY);
    const middle = (to - from) * pxPerDay > width ? focusDay : (from + to) / 2;
    return { pxPerDay, originDay: middle - width / 2 / pxPerDay };
  };

  /** The line at a place of the window, counted in lines from the first one: 1.5 is the middle of the second. */
  const getLineAt = ({ clientY }: TPosition) => {
    if (!scroll) return 0;
    return (clientY - scroll.getBoundingClientRect().top - HEADER_HEIGHT + scroll.scrollTop) / BLOCK_HEIGHT;
  };

  const { view, isPanning, showView, getDayAt, handlePointerDown } = useTimelineView(scroll, canvas, getInitialView);

  /**
   * A drag of a task, in the direction of its first movement. Sideways it is an operation on the plan: `change`
   * gives the plan for the day `getDay` reads at the pointer, and no day means the plan as it was. Up or down it
   * moves the line of the task: the line goes with the pointer and lands before the line nearest to it.
   */
  const dragTask = (
    press: TPosition,
    taskId: string,
    getDay: (position: TPosition, plan: TPlan) => string | undefined,
    change: (plan: TPlan, day: string) => TPlan,
    onEnd?: () => void
  ) => {
    // the operation begins at the first movement sideways, and once: when it cannot begin, the drag changes nothing
    const begin = once(operation.begin);
    const pressedLine = getLineAt(press);
    let lineIndex: number | undefined;
    let plan: TPlan | undefined;
    let shownDay: string | undefined;
    trackPointer(press, {
      onMove: (position, axis) => {
        if (axis === "y") {
          if (!onLineMove) return;
          const line = getLineAt(position);
          lineIndex = clamp(Math.round(line), 0, taskIds.length);
          setDrag({ taskId, lineIndex, lineOffset: (line - pressedLine) * BLOCK_HEIGHT });
          return;
        }
        plan = begin();
        if (!plan) return;
        const day = getDay(position, plan);
        // the plan is the same for every place of the pointer in a day
        if (day === shownDay) return;
        shownDay = day;
        operation.preview(day ? change(plan, day) : plan);
        setDrag({ taskId });
      },
      onEnd: ({ isAborted }) => {
        setDrag(undefined);
        onEnd?.();
        if (shownDay && !isAborted) operation.commit();
        else if (plan) operation.abort();
        else if (lineIndex !== undefined && !isAborted) onLineMove?.(taskId, lineIndex);
      },
    });
  };

  const handleBarPress = useLatestCallback((press: React.PointerEvent, taskId: string, edge?: TTaskEdge) => {
    // a press on a bar is not a press on empty space
    press.stopPropagation();
    if (press.button !== 0 || !isEditable) return;
    const grabbedAt = getDayAt(press.clientX) - days[taskId].start;
    if (edge)
      // an edge goes to the border between two days that is nearest to the pointer
      dragTask(
        press,
        taskId,
        ({ clientX }) => getDateOfDay(Math.round(getDayAt(clientX)) - (edge === "end" ? 1 : 0)),
        (plan, day) => resizeTask(plan, taskId, edge, day)
      );
    else
      dragTask(
        press,
        taskId,
        ({ clientX }) => getDateOfDay(Math.round(getDayAt(clientX) - grabbedAt)),
        (plan, day) => moveTask(plan, taskId, day)
      );
  });

  // an entry of the list dragged onto the timeline puts its task on the day under the pointer, or at an edge of a bar
  const { anchor, followEntry } = useEntryAnchor({ taskIds, days, canvas, getDayAt, getLineAt });
  const handleEntryPress = useLatestCallback((press: React.PointerEvent, taskId: string) => {
    if (press.button !== 0 || !isEditable) return;
    const { getPlace, getPlacedPlan, release } = followEntry(taskId);
    dragTask(press, taskId, getPlace, getPlacedPlan, release);
  });

  // everything of the timeline that the wheel turns is turned by this one
  const wheelTurn = useWheelTurn(operation);

  const { link, handleHandlePress, handleArrowEndPress } = useArrowLink({
    taskIds,
    days,
    view,
    operation,
    isEditable,
    getPoint: (position) => [
      position.clientX - (canvas?.getBoundingClientRect().left ?? 0),
      getLineAt(position) * BLOCK_HEIGHT,
    ],
  });

  const handleArrowHover = useLatestCallback((arrow: TScheduleArrow | undefined) => hoverArrow(arrow?.id));

  // one thing is selected at a time: an arrow or a task
  const handleArrowClick = useLatestCallback((arrow: TScheduleArrow, click: React.MouseEvent) => {
    if (!isEditable) return;
    setSelectedRow(undefined);
    setSelectedArrow({ id: arrow.id, point: { x: click.clientX, y: click.clientY } });
  });

  // as in the List layout: a click selects, a double click opens the work item beside the timeline, and an
  // open work item view follows the selection
  const handleTaskClick = useLatestCallback((click: React.MouseEvent, taskId: string) => {
    setSelectedArrow(undefined);
    setSelectedRow({ issueId: taskId, groupId: ALL_ISSUES });
    if (click.detail > 1 || isPeekOpenOnPressRef.current)
      handleRedirection(workspaceSlug?.toString(), getIssueById(taskId), isMobile);
  });

  // Delete takes the selected task off the timeline: its dates and its arrows go, the work item stays. The
  // selected arrow has the key while its control is open.
  useDeleteKey(
    scroll,
    isEditable && !drag && !link && !selectedArrow
      ? () => {
          const taskId = listView.selectedRow?.issueId;
          if (taskId && days[taskId]) runOperation(operation, (plan) => removeTask(plan, taskId));
        }
      : undefined
  );

  useIntersectionObserver({ current: scroll }, loadMoreElement, loadMore, "100% 0% 100% 0%");

  // without a timeline nothing is selected
  useEffect(() => () => setSelectedRow(undefined), [setSelectedRow]);

  const firstLine = Math.max(0, firstLineInView - LINES_BEYOND_VIEW);
  const lastLine = firstLineInView + Math.ceil(windowHeight / BLOCK_HEIGHT) + LINES_BEYOND_VIEW;
  const overlayClassName = "pointer-events-none absolute inset-y-0 right-0 overflow-hidden";

  // The bar that shows its dates and its length: the one that is dragged, wherever the pointer is; else the one
  // under the pointer, when nothing else is going on.
  const draggedTaskId = drag && drag.lineIndex === undefined ? drag.taskId : undefined;
  const shownTaskId = drag ? draggedTaskId : link || selectedArrow ? undefined : hoveredTaskId;
  // The arrow that shows more than its text: the selected one its control; under the pointer, a conflict or a
  // link that is apart what it says, with the tasks and arrows that produce it.
  const selectedArrowId = drag || link ? undefined : selectedArrow?.id;
  const explainedArrowId = drag || link || selectedArrowId ? undefined : hoveredArrowId;
  const conflict = schedule.conflicts.find(({ arrowId }) => arrowId === explainedArrowId);
  const apartLink = schedule.apartLinks.find(({ arrowId }) => arrowId === explainedArrowId);
  const controlledArrow = selectedArrowId ? arrows.find((arrow) => arrow.id === selectedArrowId) : undefined;
  const cause = useMemo(() => {
    if (conflict) return getConflictCause(arrows, schedule, conflict);
    if (!apartLink) return NO_CAUSE;
    // the link, the arrow that holds its next task apart, and the tasks at their ends
    const arrowIds = [apartLink.arrowId, apartLink.heldByArrowId];
    const previousIds = arrows.flatMap((arrow) => (arrowIds.includes(arrow.id) ? [arrow.previousId] : []));
    return { taskIds: [apartLink.taskId, ...previousIds], arrowIds };
  }, [arrows, schedule, conflict, apartLink]);
  // A fixed task that an arrow leads to shows the day it is fixed on beside its bar: the arrow does not tell it.
  const datedTaskIds = useMemo(
    () =>
      new Set(
        arrows.flatMap((arrow) =>
          arrow.id in schedule.gaps && !followingTaskIds.has(arrow.nextId) ? [arrow.nextId] : []
        )
      ),
    [arrows, schedule.gaps, followingTaskIds]
  );
  // the arrows of a line that is moved go with it
  const arrowLineIndexes = useMemo(() => {
    const lineIndex = drag?.lineOffset === undefined ? undefined : lineIndexes.get(drag.taskId);
    if (!drag?.lineOffset || lineIndex === undefined) return lineIndexes;
    return new Map(lineIndexes).set(drag.taskId, lineIndex + drag.lineOffset / BLOCK_HEIGHT);
  }, [lineIndexes, drag]);
  // the lines in view, in pixels from the top of the first line
  const viewTop = (firstLineInView + 1) * BLOCK_HEIGHT;
  const viewBottom = (firstLineInView - 1) * BLOCK_HEIGHT + (scroll?.clientHeight ?? 0) - HEADER_HEIGHT;
  const pxPerDay = view?.pxPerDay;
  const drawnArrows = useMemo(
    () =>
      pxPerDay === undefined
        ? []
        : getDrawnArrows({ arrows, days, lineIndexes: arrowLineIndexes, firstLine, lastLine, pxPerDay }),
    [arrows, days, arrowLineIndexes, firstLine, lastLine, pxPerDay]
  );

  /** The middle of a handle, in pixels from the left edge of the timeline and the top of the first line. */
  const getHandlePoint = ({ taskId, edge }: THandle): [number, number] | undefined => {
    const task = days[taskId];
    const lineIndex = lineIndexes.get(taskId);
    if (!view || !task || lineIndex === undefined) return;
    const startX = getDayX(view, task.start);
    const endX = Math.max(getDayX(view, task.end + 1), startX + MIN_BAR_WIDTH);
    return [edge === "start" ? startX - HANDLE_DISTANCE : endX + HANDLE_DISTANCE, (lineIndex + 0.5) * BLOCK_HEIGHT];
  };
  const shownTask = shownTaskId ? days[shownTaskId] : undefined;
  const shownLineIndex = shownTaskId ? lineIndexes.get(shownTaskId) : undefined;
  // the end of the arrow that is being dragged runs to the pointer until a handle takes it
  const drawnFrom = link && (!link.target || link.refusal) ? getHandlePoint(link.from) : undefined;

  const content = (
    <div
      className={cn("relative flex h-full flex-col bg-surface-1 select-none", { "inset-0 z-[25]": isFullScreen })}
      onCopy={copyAsPlainText}
    >
      <Row className="flex shrink-0 items-center justify-end gap-2 py-2" style={{ height: GANTT_BREADCRUMBS_HEIGHT }}>
        <div className="text-11 font-medium text-tertiary">
          {taskIds.length} {t("issue.label", { count: taskIds.length })}
        </div>
        <button
          type="button"
          className="rounded-md bg-layer-transparent p-1 px-2 text-11 hover:bg-layer-transparent-hover"
          onClick={() => view && showView({ ...view, originDay: now - view.width / 2 / view.pxPerDay })}
        >
          {t("common.today")}
        </button>
        <button
          type="button"
          className="flex items-center justify-center rounded-md border border-subtle bg-layer-transparent p-1 transition-all hover:bg-layer-transparent-hover"
          aria-label={t("common.full_screen")}
          aria-pressed={isFullScreen}
          onClick={() => {
            setIsFullScreen(!isFullScreen);
            setFirstLineInView(0);
          }}
        >
          {isFullScreen ? <ArrowCollapseOutline className="h-4 w-4" /> : <FullScreenOutline className="h-4 w-4" />}
        </button>
      </Row>
      <div
        ref={setScroll}
        className={cn(
          "vertical-scrollbar relative isolate scrollbar-lg flex grow touch-pan-y flex-col overflow-x-hidden border-t-[0.5px] border-subtle",
          { "cursor-grabbing": isPanning }
        )}
        onScroll={(e) => setFirstLineInView(Math.floor(e.currentTarget.scrollTop / BLOCK_HEIGHT))}
        // the work item view beside the timeline closes on a press outside it, before the click arrives
        onPointerDownCapture={() => (isPeekOpenOnPressRef.current = !!peekIssue)}
        onPointerDown={handlePointerDown}
      >
        <div className="sticky top-0 z-[4] flex shrink-0 bg-surface-1" style={{ height: HEADER_HEIGHT }}>
          <Row
            className="flex shrink-0 items-end justify-between gap-2 border-r-[0.5px] border-b-[0.5px] border-subtle-1 pb-2 text-13 font-medium text-tertiary"
            style={{ width: SIDEBAR_WIDTH }}
          >
            <div className="flex items-center gap-2">
              <h6>{t("issue.label", { count: 2 })}</h6>
              <div className="flex items-center">
                {[true, false].map((isOnlyLeaves) => (
                  <Tooltip
                    key={`${isOnlyLeaves}`}
                    label={t(isOnlyLeaves ? "timeline.leaves_description" : "issue.all")}
                  >
                    <button
                      type="button"
                      className={cn(
                        "rounded-md bg-layer-transparent px-2 py-0.5 text-11 hover:bg-layer-transparent-hover",
                        { "bg-layer-transparent-selected": showOnlyLeaves === isOnlyLeaves }
                      )}
                      aria-pressed={showOnlyLeaves === isOnlyLeaves}
                      onClick={() => onShowOnlyLeavesChange(isOnlyLeaves)}
                    >
                      {t(isOnlyLeaves ? "timeline.leaves" : "common.all")}
                    </button>
                  </Tooltip>
                ))}
              </div>
            </div>
            <h6>{t("common.duration")}</h6>
          </Row>
          <div className="relative grow overflow-hidden border-b-[0.5px] border-subtle-1">
            {view && (
              <>
                <TimelineHeader view={view} today={Math.floor(now)} startOfWeek={startOfWeek} />
                <div
                  className="absolute bottom-0 size-2 -translate-x-1/2 translate-y-1/2 rounded-full bg-accent-primary"
                  style={{ left: getDayX(view, now) }}
                />
              </>
            )}
          </div>
        </div>
        <div className="relative shrink-0 grow" style={{ minHeight: taskIds.length * BLOCK_HEIGHT }}>
          <div
            className="absolute inset-y-0 left-0 border-r-[0.5px] border-subtle-1"
            style={{ width: SIDEBAR_WIDTH }}
          />
          <div ref={setCanvas} className="absolute inset-y-0 right-0 overflow-hidden" style={{ left: SIDEBAR_WIDTH }}>
            {view && <TimelineBackdrop view={view} startOfWeek={startOfWeek} />}
          </div>
          {view && (
            <TimelineViewContext.Provider value={view}>
              <TimelineDaysContext.Provider value={days}>
                {taskIds.slice(firstLine, lastLine).map((taskId, index) => (
                  <TimelineLine
                    key={taskId}
                    taskId={taskId}
                    lineIndex={firstLine + index}
                    slack={schedule.slack[taskId] ?? 0}
                    isFixed={!followingTaskIds.has(taskId)}
                    isCritical={schedule.criticalTaskIds.includes(taskId)}
                    isConflictCause={cause.taskIds.includes(taskId)}
                    isEditable={isEditable}
                    moveOffset={drag?.taskId === taskId ? drag.lineOffset : undefined}
                    areHandlesShown={!!link && (!link.ownTaskId || link.ownTaskId === taskId)}
                    linkedEdge={[link?.target, anchor].find((handle) => handle?.taskId === taskId)?.edge}
                    isLinkRefused={!!link?.refusal}
                    onBarPress={handleBarPress}
                    onBarHover={handleBarHover}
                    onHandlePress={handleHandlePress}
                    onEntryPress={handleEntryPress}
                    onClick={handleTaskClick}
                  />
                ))}
              </TimelineDaysContext.Provider>
              {/* above the lines and below the bars; what can be pressed here is not empty space */}
              <div
                className={cn(overlayClassName, "z-[1]")}
                style={{ left: SIDEBAR_WIDTH }}
                onPointerDown={(e) => e.stopPropagation()}
              >
                <MilestoneTimelineMarkers />
                <TimelineArrows
                  view={view}
                  drawnArrows={drawnArrows}
                  schedule={schedule}
                  selectedArrowId={selectedArrowId}
                  causeArrowIds={cause.arrowIds}
                  // during a gesture no end of an arrow is taken
                  isEditable={isEditable && !drag && !link}
                  onClick={handleArrowClick}
                  onHover={handleArrowHover}
                  onEndPress={handleArrowEndPress}
                />
              </div>
              {/* above the bars */}
              <div
                className={cn(overlayClassName, "z-[3]")}
                style={{ left: SIDEBAR_WIDTH }}
                onPointerDown={(e) => e.stopPropagation()}
              >
                <TimelineArrowTexts
                  view={view}
                  drawnArrows={drawnArrows}
                  days={days}
                  lineIndexes={arrowLineIndexes}
                  firstLine={firstLine}
                  lastLine={lastLine}
                  plan={props.plan}
                  schedule={schedule}
                  datedTaskIds={datedTaskIds}
                  viewTop={viewTop}
                  viewBottom={viewBottom}
                  wheelTurn={wheelTurn}
                  // during a gesture the wheel over a text changes nothing
                  isEditable={isEditable && !drag && !link}
                  scroll={scroll}
                  onClick={handleArrowClick}
                  onHover={handleArrowHover}
                />
                {conflict && (
                  <TimelineArrowControls
                    view={view}
                    drawnArrows={drawnArrows.filter(({ arrow }) => arrow.id === conflict.arrowId)}
                    viewTop={viewTop}
                    viewBottom={viewBottom}
                    renderControl={(arrow, isNextBelow) => (
                      <TimelineConflict
                        conflict={conflict}
                        arrow={arrow}
                        operation={operation}
                        isEditable={isEditable}
                        isNextBelow={isNextBelow}
                        onClose={() => setHoveredArrowId(undefined)}
                        onPointerEnter={() => handleArrowHover(arrow)}
                        onPointerLeave={() => handleArrowHover(undefined)}
                      />
                    )}
                  />
                )}
                {apartLink && (
                  <TimelineArrowControls
                    view={view}
                    drawnArrows={drawnArrows.filter(({ arrow }) => arrow.id === apartLink.arrowId)}
                    viewTop={viewTop}
                    viewBottom={viewBottom}
                    renderControl={(arrow, isNextBelow) => (
                      <TimelineApartLink
                        apartLink={apartLink}
                        arrow={arrow}
                        heldByArrow={arrows.find((other) => other.id === apartLink.heldByArrowId)}
                        operation={operation}
                        isEditable={isEditable}
                        isNextBelow={isNextBelow}
                        onClose={() => setHoveredArrowId(undefined)}
                        onPointerEnter={() => handleArrowHover(arrow)}
                        onPointerLeave={() => handleArrowHover(undefined)}
                      />
                    )}
                  />
                )}
                {controlledArrow && selectedArrow && (
                  <TimelineArrowControl
                    key={controlledArrow.id}
                    arrow={controlledArrow}
                    schedule={schedule}
                    isNextFixed={!followingTaskIds.has(controlledArrow.nextId)}
                    operation={operation}
                    weekStartsOn={startOfWeek}
                    point={selectedArrow.point}
                    onClose={() => {
                      setSelectedArrow(undefined);
                      setHoveredArrowId(undefined);
                    }}
                  />
                )}
                <TimelineDateMarkers
                  view={view}
                  days={days}
                  lineIndexes={arrowLineIndexes}
                  firstLine={firstLine}
                  lastLine={lastLine}
                  plan={props.plan}
                  schedule={schedule}
                  datedTaskIds={datedTaskIds}
                  shownTaskId={shownTaskId}
                  wheelTurn={wheelTurn}
                  isEditable={isEditable && !drag && !link}
                  onHover={handleBarHover}
                />
                {shownTaskId && shownTask && shownLineIndex !== undefined && (
                  <TimelineBarDimension
                    view={view}
                    taskId={shownTaskId}
                    start={shownTask.start}
                    end={shownTask.end}
                    lineIndex={shownLineIndex}
                    isBelow={shownLineIndex <= firstLineInView}
                    wheelTurn={wheelTurn}
                    isEditable={isEditable && !drag && !link}
                    onHover={handleBarHover}
                  />
                )}
                {link && drawnFrom && (
                  <TimelineDrawnArrow from={drawnFrom} to={link.pointer} isRefused={!!link.refusal} />
                )}
                {link?.refusal && (
                  <div
                    className="absolute rounded-sm border border-danger-strong bg-surface-1 px-1.5 py-0.5 text-caption-md-regular whitespace-nowrap text-danger-primary shadow-raised-100"
                    style={{ left: link.pointer[0] + 14, top: link.pointer[1] + 10 }}
                  >
                    {t(`timeline.arrow.refused.${link.refusal}`)}
                  </div>
                )}
                <div className="absolute inset-y-0 w-px bg-accent-primary" style={{ left: getDayX(view, now) }} />
              </div>
            </TimelineViewContext.Provider>
          )}
          {drag?.lineIndex !== undefined && (
            <div className="absolute inset-x-0 z-[3]" style={{ top: drag.lineIndex * BLOCK_HEIGHT - 1 }}>
              <DropIndicator isVisible />
            </div>
          )}
          {loadMore && (
            <div
              ref={setLoadMoreElement}
              className="absolute h-px w-full"
              style={{ top: taskIds.length * BLOCK_HEIGHT }}
            />
          )}
        </div>
      </div>
      {quickAdd}
    </div>
  );

  const portalContainer = document.getElementById("full-screen-portal");
  return isFullScreen && portalContainer ? createPortal(content, portalContainer) : content;
});
