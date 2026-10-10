/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { minBy } from "lodash-es";
import { useState } from "react";
// plane imports
import { addArrow, placeTask } from "@plane/blocks/timeline-schedule";
import type { TPlan } from "@plane/blocks/timeline-schedule";
// local imports
import { getDateOfDay } from "./scale";
import type { THandle } from "./use-arrow-link";

type TPosition = { clientX: number; clientY: number };

type TParams = {
  taskIds: string[];
  // the first and the last day of every task that has a bar
  days: Record<string, { start: number; end: number } | undefined>;
  // the element as wide as the timeline
  canvas: HTMLElement | null;
  // the day at a place of the window, with the part of the day that lies before that place
  getDayAt: (clientX: number) => number;
  // the line at a place of the window, counted in lines from the first one
  getLineAt: (position: TPosition) => number;
};

// An edge of a bar takes the task that is dragged when the pointer is on the line of the bar and this near to the
// edge, in pixels. The task leaves the edge when the pointer is further than this to the left of it.
const ANCHOR_REACH = 20;
// And when the pointer is no faster than this, in pixels a millisecond: a hand that aims at an edge slows down,
// and a pointer on its way elsewhere passes the edges of other bars faster.
const ANCHOR_SPEED = 0.3;

/**
 * A task dragged from the list onto the timeline is put on the day under the pointer, fixed there. A task that
 * comes after another is better said so than put on a day: near an edge of a bar the dragged task takes that
 * edge as its anchor. It then follows a new arrow from that edge, from an end to its start or from a start to
 * its start: "immediately" at the edge, and with a delay of the days the pointer is to the right of it. It keeps
 * the anchor wherever the pointer goes, until that is to the left of the edge or near another edge.
 */
export const useEntryAnchor = (params: TParams) => {
  const { taskIds, days, canvas, getDayAt, getLineAt } = params;
  // states
  // the edge that the dragged task follows, for marking it
  const [anchor, setAnchor] = useState<THandle>();

  /** One drag of the entry of a task: where the task is put at a place of the pointer, and the plan with it there. */
  const followEntry = (taskId: string) => {
    // The bars are where they stood when the drag began: the preview moves the dragged task and what follows it,
    // and none of those can be its anchor.
    const barDays = days;
    let heldAnchor: THandle | undefined;
    let placedPlan: TPlan | undefined;
    let lastMove: (TPosition & { time: number }) | undefined;

    /** The day at which an edge stands: a task that follows it "immediately" starts on that day. */
    const getEdgeDay = ({ taskId: barTaskId, edge }: THandle) => {
      const bar = barDays[barTaskId];
      return bar ? (edge === "start" ? bar.start : bar.end + 1) : Infinity;
    };

    const getEdgeNear = (position: TPosition): THandle | undefined => {
      const barTaskId = taskIds[Math.floor(getLineAt(position))];
      if (!barTaskId || barTaskId === taskId || !barDays[barTaskId]) return;
      const pointerDay = getDayAt(position.clientX);
      const reach = getDayAt(position.clientX + ANCHOR_REACH) - pointerDay;
      const edges = (["start", "end"] as const).map((edge) => ({ taskId: barTaskId, edge }));
      return minBy(
        edges.filter((edge) => Math.abs(getEdgeDay(edge) - pointerDay) <= reach),
        (edge) => Math.abs(getEdgeDay(edge) - pointerDay)
      );
    };

    /** The plan with the task following a new arrow from an edge; nothing when the engine refuses that arrow. */
    const getAnchoredPlan = (plan: TPlan, day: number, edge: THandle) => {
      const placed = placeTask(plan, taskId, getDateOfDay(day));
      const delay = Math.max(day - getEdgeDay(edge), 0);
      const anchored = addArrow(placed, edge.taskId, taskId, `${edge.edge}-start`, delay);
      return "refused" in anchored ? undefined : anchored;
    };

    const release = () => {
      heldAnchor = undefined;
      setAnchor(undefined);
    };

    /**
     * Where the task is put at a place of the pointer: the same answer for every place that gives the same plan,
     * and nothing over the list, where it is put nowhere.
     */
    const getPlace = (position: TPosition, plan: TPlan): string | undefined => {
      const time = performance.now();
      const isSlow =
        !!lastMove &&
        Math.hypot(position.clientX - lastMove.clientX, position.clientY - lastMove.clientY) <=
          ANCHOR_SPEED * (time - lastMove.time);
      lastMove = { clientX: position.clientX, clientY: position.clientY, time };
      if (!canvas || position.clientX < canvas.getBoundingClientRect().left) {
        release();
        return;
      }

      const day = Math.floor(getDayAt(position.clientX));
      const edgeNear = isSlow ? getEdgeNear(position) : undefined;
      const isAtAnotherEdge = edgeNear?.taskId !== heldAnchor?.taskId || edgeNear?.edge !== heldAnchor?.edge;
      // an edge that cannot take the arrow does not take the task: the anchor it has stays
      if (edgeNear && isAtAnotherEdge && getAnchoredPlan(plan, day, edgeNear)) heldAnchor = edgeNear;
      else if (heldAnchor && getDayAt(position.clientX + ANCHOR_REACH) < getEdgeDay(heldAnchor)) heldAnchor = undefined;
      setAnchor(heldAnchor);
      placedPlan = (heldAnchor && getAnchoredPlan(plan, day, heldAnchor)) ?? placeTask(plan, taskId, getDateOfDay(day));
      return heldAnchor
        ? `${heldAnchor.taskId} ${heldAnchor.edge} ${Math.max(day - getEdgeDay(heldAnchor), 0)}`
        : getDateOfDay(day);
    };

    return { getPlace, getPlacedPlan: (plan: TPlan) => placedPlan ?? plan, release };
  };

  return { anchor, followEntry };
};
