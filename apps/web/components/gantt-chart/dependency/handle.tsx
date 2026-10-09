/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RefObject } from "react";
import { useEffect, useRef } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { disableNativeDragPreview } from "@atlaskit/pragmatic-drag-and-drop/element/disable-native-drag-preview";

export const GANTT_DEPENDENCY_DRAG = "GANTT_DEPENDENCY";

type Props = {
  blockId: string;
  blockRef: RefObject<HTMLDivElement | null>;
};

/**
 * Connector of a timeline block: it is dragged onto the block that depends on this one, and the whole
 * block accepts the connectors of the other blocks.
 */
export function DependencyHandle(props: Props) {
  const { blockId, blockRef } = props;
  // refs
  const handleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleElement = handleRef.current;
    const blockElement = blockRef.current;
    if (!handleElement || !blockElement) return;

    return combine(
      draggable({
        element: handleElement,
        getInitialData: () => ({ dragInstanceId: GANTT_DEPENDENCY_DRAG, blockId }),
        onGenerateDragPreview: ({ nativeSetDragImage }) => disableNativeDragPreview({ nativeSetDragImage }),
      }),
      dropTargetForElements({
        element: blockElement,
        canDrop: ({ source }) =>
          source.data.dragInstanceId === GANTT_DEPENDENCY_DRAG && source.data.blockId !== blockId,
        getData: () => ({ blockId }),
      })
    );
  }, [blockId, blockRef]);

  return (
    <div
      ref={handleRef}
      className="absolute top-1/2 -right-4.5 z-[6] size-3 -translate-y-1/2 cursor-crosshair rounded-full border-2 border-accent-strong bg-surface-1 opacity-0 transition-opacity group-hover:opacity-100"
    />
  );
}
