/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { pointerOutsideOfPreview } from "@atlaskit/pragmatic-drag-and-drop/element/pointer-outside-of-preview";
import { setCustomNativeDragPreview } from "@atlaskit/pragmatic-drag-and-drop/element/set-custom-native-drag-preview";
import { autoScrollForElements } from "@atlaskit/pragmatic-drag-and-drop-auto-scroll/element";
import type { Edge } from "@atlaskit/pragmatic-drag-and-drop-hitbox/closest-edge";
import { attachClosestEdge, extractClosestEdge } from "@atlaskit/pragmatic-drag-and-drop-hitbox/closest-edge";
import { sortBy } from "lodash-es";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { createRoot } from "react-dom/client";
// plane imports
import { DragHandle, DropIndicator } from "@plane/blocks/common";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// hooks
import { useAppTheme } from "@/hooks/store/use-app-theme";
import { useWorkspace } from "@/hooks/store/use-workspace";

/** The sections in the order they have until the user moves one. */
const SIDEBAR_SECTION_KEYS = ["personal", "workspace", "favorites", "projects"] as const;
export type TSidebarSectionKey = (typeof SIDEBAR_SECTION_KEYS)[number];

/**
 * The order is kept with the user's other choices for the sidebar of a workspace (which entries are shown, in
 * which order), under one key per section.
 */
const getPreferenceKey = (sectionKey: TSidebarSectionKey) => `section_${sectionKey}`;

/** Keeps the drags of sections apart from the other drags of the sidebar (projects, favorites). */
const DRAG_INSTANCE_ID = "SIDEBAR_SECTIONS";

const useSidebarSectionOrder = () => {
  const { workspaceSlug } = useParams();
  const { getNavigationPreferences, updateBulkSidebarPreferences } = useWorkspace();
  const preferences = getNavigationPreferences(workspaceSlug?.toString() ?? "");

  const getPosition = (sectionKey: TSidebarSectionKey) =>
    preferences?.[getPreferenceKey(sectionKey)]?.sort_order ?? SIDEBAR_SECTION_KEYS.indexOf(sectionKey);
  const order = sortBy(SIDEBAR_SECTION_KEYS, getPosition);

  const moveSection = (source: TSidebarSectionKey, target: TSidebarSectionKey, edge: Edge | null) => {
    if (!workspaceSlug || source === target) return;
    const next = order.filter((sectionKey) => sectionKey !== source);
    next.splice(next.indexOf(target) + (edge === "bottom" ? 1 : 0), 0, source);
    void updateBulkSidebarPreferences(
      workspaceSlug.toString(),
      next.map((sectionKey, index) => ({
        key: getPreferenceKey(sectionKey),
        is_pinned: preferences?.[getPreferenceKey(sectionKey)]?.is_pinned ?? false,
        sort_order: index,
      }))
    );
  };

  return { order, moveSection };
};

type TSidebarSectionProps = {
  sectionKey: TSidebarSectionKey;
  /** Shown beside the pointer while the section is dragged. */
  label: string;
  /** A section with a heading is dragged by it; one without gets a handle of its own. */
  hasHeading: boolean;
  isLast: boolean;
  onMove: (source: TSidebarSectionKey, target: TSidebarSectionKey, edge: Edge | null) => void;
  children: ReactNode;
};

const SidebarSection = observer(function SidebarSection(props: TSidebarSectionProps) {
  const { sectionKey, label, hasHeading, isLast, onMove, children } = props;
  // states
  const [isDragging, setIsDragging] = useState(false);
  const [closestEdge, setClosestEdge] = useState<Edge | null>(null);
  // refs
  const sectionRef = useRef<HTMLDivElement | null>(null);
  const handleRef = useRef<HTMLButtonElement | null>(null);
  // store hooks
  const { sidebarCollapsed } = useAppTheme();

  useEffect(() => {
    const element = sectionRef.current;
    if (!element) return;
    // the heading of a section is the header of its collapsible: the part around the button that folds it
    const heading = hasHeading ? element.querySelector("button[aria-expanded]")?.parentElement : handleRef.current;

    return combine(
      draggable({
        element,
        dragHandle: heading ?? undefined,
        canDrag: () => !sidebarCollapsed,
        getInitialData: () => ({ dragInstanceId: DRAG_INSTANCE_ID, sectionKey }),
        onDragStart: () => setIsDragging(true),
        onDrop: () => setIsDragging(false),
        // the section itself would be a picture as tall as the list of projects
        onGenerateDragPreview: ({ nativeSetDragImage }) => {
          setCustomNativeDragPreview({
            getOffset: pointerOutsideOfPreview({ x: "0px", y: "0px" }),
            render: ({ container }) => {
              const root = createRoot(container);
              root.render(<div className="rounded-sm bg-surface-1 px-2 py-1 text-13 text-secondary">{label}</div>);
              return () => root.unmount();
            },
            nativeSetDragImage,
          });
        },
      }),
      dropTargetForElements({
        element,
        canDrop: ({ source }) =>
          source.data.dragInstanceId === DRAG_INSTANCE_ID && source.data.sectionKey !== sectionKey,
        getData: ({ input, element: target }) =>
          attachClosestEdge({ sectionKey }, { input, element: target, allowedEdges: ["top", "bottom"] }),
        onDrag: ({ self }) => setClosestEdge(extractClosestEdge(self.data)),
        onDragLeave: () => setClosestEdge(null),
        onDrop: ({ self, source }) => {
          setClosestEdge(null);
          onMove(source.data.sectionKey as TSidebarSectionKey, sectionKey, extractClosestEdge(self.data));
        },
      })
    );
  }, [sectionKey, label, hasHeading, sidebarCollapsed, onMove]);

  return (
    <div ref={sectionRef} className={cn("group/sidebar-section relative", { "opacity-60": isDragging })}>
      {/* The lines stand in the middle of the gap between two sections. Under the last section there is no gap:
          a line below it would make the sidebar a few pixels longer than it is. */}
      {closestEdge === "top" && <DropIndicator classNames="absolute -top-[7px]" isVisible />}
      {!hasHeading && (
        <DragHandle
          ref={handleRef}
          className="absolute top-1.5 -left-3 bg-transparent opacity-0 group-hover/sidebar-section:opacity-100"
        />
      )}
      {children}
      {closestEdge === "bottom" && (
        <DropIndicator classNames={cn("absolute", isLast ? "bottom-0" : "-bottom-[7px]")} isVisible />
      )}
    </div>
  );
});

type TSidebarSectionsProps = {
  /** What each section shows; a section that is not shown now has no content. */
  sections: Record<TSidebarSectionKey, ReactNode>;
};

/**
 * The sections of the sidebar, each of which the user can drag to another place among them.
 */
export const SidebarSections = observer(function SidebarSections(props: TSidebarSectionsProps) {
  const { sections } = props;
  // refs
  const sectionsRef = useRef<HTMLDivElement | null>(null);
  // hooks
  const { t } = useTranslation();
  const { order, moveSection } = useSidebarSectionOrder();

  // A section held at the upper or the lower edge of the sidebar scrolls it, so that the line under a long
  // last section, or over a first one that is scrolled away, comes into view.
  useEffect(() => {
    let scroller = sectionsRef.current?.parentElement;
    while (scroller && getComputedStyle(scroller).overflowY !== "scroll") scroller = scroller.parentElement;
    if (!scroller) return;
    return autoScrollForElements({
      element: scroller,
      canScroll: ({ source }) => source.data.dragInstanceId === DRAG_INSTANCE_ID,
      getAllowedAxis: () => "vertical",
    });
  }, []);

  const labels: Record<TSidebarSectionKey, string> = {
    personal: t("personal"),
    workspace: t("common.workspace"),
    favorites: t("favorites"),
    projects: t("projects"),
  };

  const shownSections = order.filter((sectionKey) => sections[sectionKey]);

  return (
    // without a box of its own, so that the sections stay the items of the column they stand in
    <div ref={sectionsRef} className="contents">
      {shownSections.map((sectionKey, index) => (
        <SidebarSection
          key={sectionKey}
          sectionKey={sectionKey}
          label={labels[sectionKey]}
          hasHeading={sectionKey !== "personal"}
          isLast={index === shownSections.length - 1}
          onMove={moveSection}
        >
          {sections[sectionKey]}
        </SidebarSection>
      ))}
    </div>
  );
});
