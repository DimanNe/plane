/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RefObject } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { monitorForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane imports
import { PROJECT_TIMELINE_DEPENDENCIES } from "@plane/constants";
import type { IGanttBlock, TTimelineDependency } from "@plane/types";
// hooks
import { useUserPermissions } from "@/hooks/store/user";
import { useIssuesTimeLineStore } from "@/hooks/use-timeline-chart";
// local imports
import { BLOCK_HEIGHT } from "../constants";
import { GANTT_DEPENDENCY_DRAG } from "./handle";
import type { TTimelineRelation } from "./relation-modal";
import { TimelineRelationModal } from "./relation-modal";

type TPoint = { x: number; y: number };

type TRowIndexMap = Map<string, number>;

const ARROW_LENGTH = 6;
const MIN_CURVE_WIDTH = 32;

/** A dependency leaves and reaches a block at its start or its finish, in the middle of the block's row. */
const getBlockAnchor = (
  block: IGanttBlock | undefined,
  rowIndex: number | undefined,
  side: "start" | "finish"
): TPoint | undefined => {
  if (!block?.position || !block.start_date || !block.target_date || rowIndex === undefined) return;
  return {
    x: block.position.marginLeft + (side === "finish" ? block.position.width : 0),
    y: rowIndex * BLOCK_HEIGHT + BLOCK_HEIGHT / 2,
  };
};

/** `fromDirection` and `toDirection` are -1 when the line leaves or arrives on the left of its anchor, 1 on the right. */
const getCurve = (from: TPoint, to: TPoint, fromDirection: number, toDirection: number) => {
  const curveWidth = Math.max(MIN_CURVE_WIDTH, Math.abs(to.x - from.x) / 2);
  return `M ${from.x} ${from.y} C ${from.x + fromDirection * curveWidth} ${from.y}, ${to.x + toDirection * curveWidth} ${to.y}, ${to.x} ${to.y}`;
};

type TDependencyPathProps = {
  dependency: TTimelineDependency;
  rowIndexMap: TRowIndexMap;
  onClick: (dependency: TTimelineDependency) => void;
};

const DependencyPath = observer(function DependencyPath(props: TDependencyPathProps) {
  const { dependency, rowIndexMap, onClick } = props;
  const { predecessor_id, dependent_id, relation_type } = dependency;
  // store hooks
  const { getBlockById, getIsDependencyViolated } = useIssuesTimeLineStore();
  // derived values
  const from = getBlockAnchor(
    getBlockById(predecessor_id),
    rowIndexMap.get(predecessor_id),
    relation_type === "start_before" ? "start" : "finish"
  );
  const to = getBlockAnchor(
    getBlockById(dependent_id),
    rowIndexMap.get(dependent_id),
    relation_type === "finish_before" ? "finish" : "start"
  );

  if (!from || !to) return null;

  const fromDirection = relation_type === "start_before" ? -1 : 1;
  const toDirection = relation_type === "finish_before" ? 1 : -1;
  const curve = getCurve(from, to, fromDirection, toDirection);

  return (
    <g className={getIsDependencyViolated(dependency) ? "text-danger-primary" : "text-accent-primary"}>
      <path d={curve} fill="none" stroke="currentColor" strokeWidth={1.5} />
      <path
        d={`M ${to.x} ${to.y} l ${toDirection * ARROW_LENGTH} -4 v 8 z`}
        fill="currentColor"
        stroke="currentColor"
        strokeLinejoin="round"
      />
      <path
        d={curve}
        fill="none"
        stroke="transparent"
        strokeWidth={12}
        className="[pointer-events:stroke] cursor-pointer"
        onClick={() => onClick(dependency)}
      />
    </g>
  );
});

type TDependencyDragPreviewProps = {
  svgRef: RefObject<SVGSVGElement | null>;
  rowIndexMap: TRowIndexMap;
  onDrop: (predecessorId: string, dependentId: string) => void;
};

/** Follows the connector of a block while it is dragged, and reports the block it is dropped on. */
const DependencyDragPreview = observer(function DependencyDragPreview(props: TDependencyDragPreviewProps) {
  const { svgRef, rowIndexMap, onDrop } = props;
  // states
  const [drag, setDrag] = useState<{ blockId: string; pointer: TPoint } | null>(null);
  // store hooks
  const { getBlockById } = useIssuesTimeLineStore();

  useEffect(
    () =>
      monitorForElements({
        canMonitor: ({ source }) => source.data.dragInstanceId === GANTT_DEPENDENCY_DRAG,
        onDrag: ({ source, location }) => {
          const bounds = svgRef.current?.getBoundingClientRect();
          if (!bounds) return;
          const { clientX, clientY } = location.current.input;
          setDrag({
            blockId: source.data.blockId as string,
            pointer: { x: clientX - bounds.left, y: clientY - bounds.top },
          });
        },
        onDrop: ({ source, location }) => {
          setDrag(null);
          const dependentId = location.current.dropTargets[0]?.data.blockId;
          if (dependentId) onDrop(source.data.blockId as string, dependentId as string);
        },
      }),
    [svgRef, onDrop]
  );

  const from = drag && getBlockAnchor(getBlockById(drag.blockId), rowIndexMap.get(drag.blockId), "finish");

  if (!drag || !from) return null;

  return (
    <path
      d={getCurve(from, drag.pointer, 1, -1)}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeDasharray="4 3"
      className="text-accent-primary"
    />
  );
});

type Props = {
  blockIds: string[];
  isEditable: boolean;
};

export const TimelineDependencyPaths = observer(function TimelineDependencyPaths(props: Props) {
  const { blockIds, isEditable } = props;
  // router
  const { workspaceSlug, projectId } = useParams();
  // refs
  const svgRef = useRef<SVGSVGElement>(null);
  // states
  const [relation, setRelation] = useState<TTimelineRelation | null>(null);
  // store hooks
  const { getProjectDependencies, fetchDependencies } = useIssuesTimeLineStore();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  // derived values
  const rowIndexMap: TRowIndexMap = useMemo(
    () => new Map(blockIds.map((blockId, index) => [blockId, index])),
    [blockIds]
  );
  const dependencies = getProjectDependencies(projectId.toString());
  const currentProjectRole = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug.toString(), projectId.toString());

  useSWR(
    PROJECT_TIMELINE_DEPENDENCIES(projectId.toString(), currentProjectRole),
    () => fetchDependencies(workspaceSlug.toString(), projectId.toString()),
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  const handleDependencyClick = useCallback(
    (dependency: TTimelineDependency) =>
      setRelation({ predecessorId: dependency.predecessor_id, dependentId: dependency.dependent_id, dependency }),
    []
  );

  const handleConnectorDrop = useCallback(
    (predecessorId: string, dependentId: string) => setRelation({ predecessorId, dependentId }),
    []
  );

  return (
    <>
      <svg ref={svgRef} className="pointer-events-none absolute top-0 left-0 z-[4] h-full w-full overflow-visible">
        {dependencies.map((dependency) => (
          <DependencyPath
            key={dependency.id}
            dependency={dependency}
            rowIndexMap={rowIndexMap}
            onClick={handleDependencyClick}
          />
        ))}
        <DependencyDragPreview svgRef={svgRef} rowIndexMap={rowIndexMap} onDrop={handleConnectorDrop} />
      </svg>
      {relation && (
        <TimelineRelationModal relation={relation} isEditable={isEditable} handleClose={() => setRelation(null)} />
      )}
    </>
  );
});
