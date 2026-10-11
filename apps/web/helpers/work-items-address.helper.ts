/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { EIssueLayoutTypes } from "@plane/types";

/**
 * The address of a project's work items as the user sees and types it:
 *
 *   /<workspace>/<project identifier>/             the List layout
 *   /<workspace>/<project identifier>/<layout>/    another layout
 *   /<workspace>/<project identifier>-<number>/    that work item selected and its panel open
 *
 * It ends in a slash as every address of the app does: the app turns an address without one into one with it by a
 * step in the history, which a reload would then add each time.
 *
 * The router goes on knowing the page as /<workspace>/projects/<project id>/issues/, which is what the many
 * components and stores that take the project from the route read. The short address is laid over it as the
 * router's mask. This module is the one place that writes a short address and reads one back.
 */
export type TWorkItemsAddress = {
  workspaceSlug: string;
  projectIdentifier: string;
  /** Absent with a work item: its address says nothing of the layout, and the page keeps the one it has. */
  layout?: EIssueLayoutTypes;
  sequenceId?: string;
};

const LAYOUT_WORDS: Partial<Record<EIssueLayoutTypes, string>> = {
  [EIssueLayoutTypes.KANBAN]: "board",
  [EIssueLayoutTypes.GANTT]: "timeline",
  [EIssueLayoutTypes.CALENDAR]: "calendar",
  [EIssueLayoutTypes.SPREADSHEET]: "table",
};

/**
 * The first word of every page of a workspace (app/routes/core.ts). The router gives /<workspace>/<word> to that
 * page, so a project whose identifier is one of these words has no short address and keeps the long one.
 */
export const WORKSPACE_PAGE_WORDS = [
  "active-cycles",
  "analytics",
  "browse",
  "drafts",
  "notifications",
  "profile",
  "projects",
  "settings",
  "stickies",
  "wiki",
  "workspace-views",
];

/** Letters and digits, as the project form allows. The API also lets through characters that an address cannot hold. */
const IDENTIFIER_PATTERN = /^[\p{L}\p{N}]+$/u;

const hasShortAddress = (projectIdentifier: string) =>
  IDENTIFIER_PATTERN.test(projectIdentifier) && !WORKSPACE_PAGE_WORDS.includes(projectIdentifier.toLowerCase());

const decodeSegment = (segment: string) => {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
};

/** Identifiers are written in lower case in an address and accepted in any case. */
export const isSameProjectIdentifier = (one: string, other: string) => one.toLowerCase() === other.toLowerCase();

export const getWorkItemsRoute = (workspaceSlug: string, projectId: string) =>
  `/${workspaceSlug}/projects/${projectId}/issues/`;

/** The short address, or nothing for a project that cannot have one. */
export const getWorkItemsAddress = (address: TWorkItemsAddress) => {
  const { workspaceSlug, projectIdentifier, layout, sequenceId } = address;
  if (!hasShortAddress(projectIdentifier)) return undefined;
  const project = `/${workspaceSlug}/${encodeURIComponent(projectIdentifier.toLowerCase())}`;
  if (sequenceId !== undefined) return `${project}-${sequenceId}/`;
  const layoutWord = layout && LAYOUT_WORDS[layout];
  return layoutWord ? `${project}/${layoutWord}/` : `${project}/`;
};

/** What a short address names, or nothing when the path is not one. */
export const parseWorkItemsAddress = (pathname: string): TWorkItemsAddress | undefined => {
  const [workspaceSlug, project, layoutWord, ...rest] = pathname.split("/").filter(Boolean);
  if (!workspaceSlug || !project || rest.length > 0) return undefined;
  const [, identifierSegment = project, sequenceId] = /^(.+)-(\d+)$/.exec(project) ?? [];
  const projectIdentifier = decodeSegment(identifierSegment);
  if (!hasShortAddress(projectIdentifier)) return undefined;
  const address = { workspaceSlug, projectIdentifier };
  if (sequenceId !== undefined) return layoutWord ? undefined : { ...address, sequenceId };
  if (!layoutWord) return { ...address, layout: EIssueLayoutTypes.LIST };
  const layout = Object.values(EIssueLayoutTypes).find((key) => LAYOUT_WORDS[key] === layoutWord);
  return layout && { ...address, layout };
};

/**
 * The browser's history, entry by entry, is where the page of a project's work items keeps what Back and Forward
 * have to bring back: the short address, and the layout, which the address of a selected work item does not name.
 *
 * The router keeps its own notes in the state of every entry, and the page writes into them: `key` names the
 * entry, `idx` counts it, `usr` is the state that goes with the location, and `masked` is the address the router
 * is on while the browser shows another (react-router, lib/router/history.ts). The page writes them itself and
 * does not ask the router to: the router answers a step with a transition, which React puts off for as long as
 * the page goes on drawing, seconds after a list has opened. A router that changes these notes would read the
 * short address as a new arrival, which still opens the right page.
 */
export type TWorkItemsEntryState = { workItemsLayout?: EIssueLayoutTypes } | null;

type TRouterEntryState = {
  key?: string;
  idx?: number;
  usr?: TWorkItemsEntryState;
  masked?: { pathname: string; search: string; hash: string };
};

export const readWorkItemsEntry = () => {
  const state = (window.history.state ?? {}) as TRouterEntryState;
  return {
    key: state.key ?? "default",
    /** The address the router is on. */
    route: state.masked?.pathname ?? window.location.pathname,
    address: state.masked ? parseWorkItemsAddress(window.location.pathname) : undefined,
    layout: state.usr?.workItemsLayout,
  };
};

type TWorkItemsEntryChange = {
  /** The short address to show. */
  address: string;
  /** The layout to take down with the entry; the one it has stays when absent. */
  layout?: EIssueLayoutTypes;
  /** A new entry after the present one, which Back returns from. */
  isNewEntry?: boolean;
};

/** Writes the present entry, or a new one after it, and returns the entry's key. */
export const writeWorkItemsEntry = ({ address, layout, isNewEntry = false }: TWorkItemsEntryChange) => {
  const state = (window.history.state ?? {}) as TRouterEntryState;
  const { pathname, search, hash } = window.location;
  const entryState: TRouterEntryState = {
    ...state,
    usr: layout ? { ...state.usr, workItemsLayout: layout } : state.usr,
    masked: state.masked ?? { pathname, search, hash },
    ...(isNewEntry && { key: Math.random().toString(36).slice(2, 10), idx: (state.idx ?? 0) + 1 }),
  };
  window.history[isNewEntry ? "pushState" : "replaceState"](entryState, "", address + search + hash);
  return entryState.key ?? "default";
};
