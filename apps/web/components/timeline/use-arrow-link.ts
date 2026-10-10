/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { once } from "lodash-es";
// plane imports
import { addArrow, changeArrow, getArrowKind } from "@plane/blocks/timeline-schedule";
import type { TPlan, TRefusal, TScheduleArrow, TTaskEdge } from "@plane/blocks/timeline-schedule";
import { useLatestCallback } from "@plane/hooks";
// components
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
// local imports
import type { TArrowEnd } from "./arrows";
import type { TTimelineOperation } from "./operation";
import { trackPointer } from "./pointer";
import type { TTimelineView } from "./scale";
import { getDayX, MIN_BAR_WIDTH } from "./scale";

/** A handle of a bar: an arrow starts from it or ends at it. */
export type THandle = { taskId: string; edge: TTaskEdge };

/** Why the handle under the pointer does not take an arrow: start to end is no kind of arrow, or the engine refuses. */
export type TLinkRefusal = TRefusal["refused"] | "no-such-kind";

/** An arrow that is being drawn from a handle, or an arrow whose end is being taken to another handle. */
export type TArrowLink = {
  // the end that stays: where a new arrow is drawn from, or the other end of the arrow
  from: THandle;
  // the bar whose handles take the end of an arrow; a new arrow is taken by any other bar
  ownTaskId?: string;
  // the pointer, in pixels from the left edge of the timeline and the top of the first line
  pointer: [x: number, y: number];
  // the handle under the pointer that takes the arrow or refuses it
  target?: THandle;
  refusal?: TLinkRefusal;
};

type TParams = {
  taskIds: string[];
  // the first and the last day of every task that has a bar
  days: Record<string, { start: number; end: number }>;
  view: TTimelineView | undefined;
  operation: TTimelineOperation;
  isEditable: boolean;
  getPoint: (position: { clientX: number; clientY: number }) => [x: number, y: number];
};

// a handle is under the pointer this far outside its bar, and over the half of the bar it is at
const HANDLE_REACH = 24;

/**
 * Drawing an arrow from a handle to a handle of another bar, and dragging an end of an arrow to the other handle
 * of its bar. Both are one operation: shown while the pointer is over a handle that takes the arrow, saved on a
 * release there.
 */
export const useArrowLink = (params: TParams) => {
  const { taskIds, days, view, operation, isEditable, getPoint } = params;
  // states
  const [link, setLink] = useState<TArrowLink>();

  const getHandleAt = useLatestCallback(([x, y]: [number, number], barDays: TParams["days"]): THandle | undefined => {
    const taskId = taskIds[Math.floor(y / BLOCK_HEIGHT)];
    const task = taskId ? barDays[taskId] : undefined;
    if (!task || !view) return;
    const startX = getDayX(view, task.start);
    const endX = Math.max(getDayX(view, task.end + 1), startX + MIN_BAR_WIDTH);
    if (x < startX - HANDLE_REACH || x > endX + HANDLE_REACH) return;
    return { taskId, edge: x < (startX + endX) / 2 ? "start" : "end" };
  });

  /**
   * `getLinkedPlan` gives the plan with the arrow at a handle, the reason the handle refuses the arrow, or nothing
   * for a handle that has nothing to do with it.
   */
  const dragLink = (
    press: React.PointerEvent,
    from: THandle,
    ownTaskId: string | undefined,
    getLinkedPlan: (plan: TPlan, handle: THandle) => TPlan | TLinkRefusal | undefined
  ) => {
    // a press on a handle or on an arrow is not a press on empty space
    press.stopPropagation();
    if (press.button !== 0 || !isEditable) return;
    // Handles are where the bars stood when the drag began: the preview moves the next task away from the pointer.
    const barDays = days;
    // the operation begins at the first movement, and once: when it cannot begin, the drag changes nothing
    const begin = once(operation.begin);
    let plan: TPlan | undefined;
    let shownTarget: THandle | undefined;
    let isLinked = false;
    trackPointer(press, {
      onMove: (position) => {
        plan = begin();
        if (!plan) return;
        const pointer = getPoint(position);
        const handle = getHandleAt(pointer, barDays);
        const linked = handle && getLinkedPlan(plan, handle);
        const target = linked ? handle : undefined;
        isLinked = typeof linked === "object";
        setLink({ from, ownTaskId, pointer, target, refusal: typeof linked === "string" ? linked : undefined });
        if (target?.taskId === shownTarget?.taskId && target?.edge === shownTarget?.edge) return;
        shownTarget = target;
        operation.preview(typeof linked === "object" ? linked : plan);
      },
      onEnd: ({ isAborted }) => {
        setLink(undefined);
        if (isLinked && !isAborted) operation.commit();
        else if (plan) operation.abort();
      },
    });
  };

  const handleHandlePress = useLatestCallback((press: React.PointerEvent, taskId: string, edge: TTaskEdge) =>
    dragLink(press, { taskId, edge }, undefined, (plan, handle) => {
      if (handle.taskId === taskId && handle.edge === edge) return;
      const kind = getArrowKind(edge, handle.edge);
      // the engine's refusals are asked for first: an arrow to the same task is refused whatever its kind
      const linked = addArrow(plan, taskId, handle.taskId, kind ?? "end-start");
      return "refused" in linked ? linked.refused : kind ? linked : "no-such-kind";
    })
  );

  const handleArrowEndPress = useLatestCallback((press: React.PointerEvent, arrow: TScheduleArrow, end: TArrowEnd) => {
    const [previousEdge, nextEdge] = arrow.kind.split("-") as [TTaskEdge, TTaskEdge];
    const ownTaskId = end === "tail" ? arrow.previousId : arrow.nextId;
    const from =
      end === "tail" ? { taskId: arrow.nextId, edge: nextEdge } : { taskId: arrow.previousId, edge: previousEdge };
    dragLink(press, from, ownTaskId, (plan, handle) => {
      if (handle.taskId !== ownTaskId || handle.edge === (end === "tail" ? previousEdge : nextEdge)) return;
      const kind = end === "tail" ? getArrowKind(handle.edge, nextEdge) : getArrowKind(previousEdge, handle.edge);
      return kind ? changeArrow(plan, arrow.id, { kind }) : "no-such-kind";
    });
  });

  return { link, handleHandlePress, handleArrowEndPress };
};
