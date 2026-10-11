/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { reaction } from "mobx";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { useLocation } from "react-router";
// plane imports
import { ALL_ISSUES, EIssueFilterType } from "@plane/constants";
import { useLatestCallback } from "@plane/hooks";
import { EIssueLayoutTypes, EIssuesStoreType } from "@plane/types";
// helpers
import type { TWorkItemsAddress } from "@/helpers/work-items-address.helper";
import {
  getWorkItemsAddress,
  isSameProjectIdentifier,
  readWorkItemsEntry,
  writeWorkItemsEntry,
} from "@/helpers/work-items-address.helper";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssues } from "@/hooks/store/use-issues";
import { useListView } from "@/hooks/store/use-list-view";
import { useProject } from "@/hooks/store/use-project";

/** The address follows the selection once it rests: a held arrow key passes many lines and writes one address. */
const ADDRESS_WRITE_DELAY = 150;
/** A layout draws its lines some time after the page has opened; a work item it does not list never gets one. */
const LINE_WAIT = { step: 100, steps: 50 };

/**
 * Where a layout shows a work item. Every layout gives that element the work item's id; the List layout draws it
 * near the visible part only and keeps a place for each line it lists, which is there to scroll to.
 */
const findLine = (workItemId: string) =>
  document.querySelector<HTMLElement>(`div[id^="issue_${workItemId}_"]`) ??
  document.getElementById(`issue-${workItemId}`);

/**
 * Keeps the address in the browser and the page of a project's work items in step, both ways. The page follows
 * the address when it is opened or come back to: the layout the address names, the work item it names selected,
 * in view, with its panel open. Afterwards the address follows the page: the layout, and the work item that is
 * selected or open. See helpers/work-items-address.helper.ts for the addresses and for the entries of the
 * browser's history.
 */
export const ProjectWorkItemsAddress = observer(function ProjectWorkItemsAddress() {
  // router
  const params = useParams();
  const workspaceSlug = params.workspaceSlug?.toString();
  const projectId = params.projectId?.toString();
  const { key: locationKey, pathname: route } = useLocation();
  // store hooks
  const { getProjectById, workspaceProjectIds } = useProject();
  const { issuesFilter } = useIssues(EIssuesStoreType.PROJECT);
  const issueDetail = useIssueDetail();
  const listView = useListView();
  // states
  const [entryKey, setEntryKey] = useState(() => readWorkItemsEntry().key);
  const [shownEntryKey, setShownEntryKey] = useState<string>();
  const [workItemIdToSelect, setWorkItemIdToSelect] = useState<string>();
  // derived values
  const getLayout = () =>
    projectId ? (issuesFilter.getIssueFilters(projectId)?.displayFilters?.layout as EIssueLayoutTypes) : undefined;
  const layout = getLayout();
  const isEntryShown = shownEntryKey === entryKey;

  /** The entry the browser is at, when it is still the one this page knows of and an entry of this page. */
  const readEntry = useLatestCallback(() => {
    const entry = readWorkItemsEntry();
    return entry.key === entryKey && entry.route === route ? entry : undefined;
  });

  const getAddress = useLatestCallback(() => {
    const project = getProjectById(projectId);
    if (!workspaceSlug || !project) return undefined;
    // the selected line is what the user touched last; the panel comes after it when a key is held
    const workItemId = listView.selectedRow?.issueId ?? issueDetail.peekIssue?.issueId;
    const workItem = workItemId ? issueDetail.issue.getIssueById(workItemId) : undefined;
    const workItemProject = getProjectById(workItem?.project_id);
    return workItem && workItemProject
      ? getWorkItemsAddress({
          workspaceSlug,
          projectIdentifier: workItemProject.identifier,
          sequenceId: workItem.sequence_id.toString(),
        })
      : getWorkItemsAddress({ workspaceSlug, projectIdentifier: project.identifier, layout: getLayout() });
  });

  /** The work item of an entry's address, or none where the address names none. */
  const showWorkItem = useLatestCallback(async (address: TWorkItemsAddress | undefined) => {
    // an entry that the router made by a link has no short address yet, and the page stays as it is
    if (!workspaceSlug || !address) return;
    if (!address.sequenceId) {
      if (issueDetail.peekIssue) issueDetail.setPeekIssue(undefined);
      if (listView.selectedRow) listView.setSelectedRow(undefined);
      return;
    }
    const projectIdentifier =
      (workspaceProjectIds ?? [])
        .map((id) => getProjectById(id)?.identifier)
        .find((identifier) => identifier && isSameProjectIdentifier(identifier, address.projectIdentifier)) ??
      address.projectIdentifier.toUpperCase();
    const workItemId =
      issueDetail.issue.getIssueIdByIdentifier(`${projectIdentifier}-${address.sequenceId}`) ??
      (await issueDetail.fetchIssueWithIdentifier(workspaceSlug, projectIdentifier, address.sequenceId)).id;
    const workItem = issueDetail.issue.getIssueById(workItemId);
    if (!workItem?.project_id) return;
    if (issueDetail.peekIssue?.issueId !== workItem.id)
      issueDetail.setPeekIssue({ workspaceSlug, projectId: workItem.project_id, issueId: workItem.id });
    setWorkItemIdToSelect(workItem.id);
  });

  const selectLine = useLatestCallback((workItemId: string, line: HTMLElement) => {
    // the List layout and the timeline keep a selected line; in the others the open panel is all there is
    if (layout === EIssueLayoutTypes.LIST || layout === EIssueLayoutTypes.GANTT)
      listView.setSelectedRow({ issueId: workItemId, groupId: ALL_ISSUES });
    line.scrollIntoView({ block: "center", inline: "nearest" });
  });

  // The browser comes to another entry by the router (a link, another project) and by Back and Forward. The
  // router tells of both, but late while the page is drawing; Back and Forward are heard from the browser itself.
  useEffect(() => {
    const takeEntryKey = () => setEntryKey(readWorkItemsEntry().key);
    takeEntryKey();
    window.addEventListener("popstate", takeEntryKey);
    return () => window.removeEventListener("popstate", takeEntryKey);
  }, [locationKey]);

  // The page takes in the entry it was opened at, or come back to.
  useEffect(() => {
    const entry = readEntry();
    if (!workspaceSlug || !projectId || !layout || isEntryShown || !entry) return;
    const layoutToShow = entry.layout ?? entry.address?.layout;
    if (layoutToShow && layoutToShow !== layout) {
      void issuesFilter.updateFilters(workspaceSlug, projectId, EIssueFilterType.DISPLAY_FILTERS, {
        layout: layoutToShow,
      });
      return;
    }
    let isSameEntry = true;
    void showWorkItem(entry.address)
      // a work item that is gone since the address was written: the page shows its layout without it
      .catch(() => {})
      .finally(() => {
        if (!isSameEntry || !readEntry()) return;
        // an entry that the router made, by a link or from an address that was typed, has no layout taken down
        const address = getAddress();
        if (!entry.layout && address) writeWorkItemsEntry({ address, layout });
        setShownEntryKey(entryKey);
      });
    return () => {
      isSameEntry = false;
    };
  }, [workspaceSlug, projectId, layout, isEntryShown, entryKey, issuesFilter, readEntry, getAddress, showWorkItem]);

  // The line of the work item that the address named is selected and brought into view once its layout has it.
  useEffect(() => {
    if (!workItemIdToSelect) return;
    let stepsLeft = LINE_WAIT.steps;
    const timer = setInterval(() => {
      const line = findLine(workItemIdToSelect);
      stepsLeft -= 1;
      if (!line && stepsLeft > 0) return;
      setWorkItemIdToSelect(undefined);
      if (line) selectLine(workItemIdToSelect, line);
    }, LINE_WAIT.step);
    return () => clearInterval(timer);
  }, [workItemIdToSelect, selectLine]);

  // A layout that the user changes is a new entry, which Back undoes.
  useEffect(() => {
    const entry = readEntry();
    const address = getAddress();
    if (!layout || !isEntryShown || !entry?.layout || entry.layout === layout || !address) return;
    const newEntryKey = writeWorkItemsEntry({ address, layout, isNewEntry: true });
    setEntryKey(newEntryKey);
    setShownEntryKey(newEntryKey);
  }, [layout, isEntryShown, readEntry, getAddress]);

  // The address follows the selected line and the panel within one entry, and nothing of the page is drawn again
  // for it.
  useEffect(() => {
    if (!isEntryShown) return;
    let timer: ReturnType<typeof setTimeout>;
    const writeAddress = () => {
      const address = getAddress();
      // an entry without a layout taken down is of a project that has no short address
      if (!readEntry()?.layout || !address || address === window.location.pathname) return;
      writeWorkItemsEntry({ address });
    };
    const stopFollowing = reaction(
      getAddress,
      () => {
        clearTimeout(timer);
        timer = setTimeout(writeAddress, ADDRESS_WRITE_DELAY);
      },
      { fireImmediately: true }
    );
    return () => {
      stopFollowing();
      clearTimeout(timer);
    };
  }, [isEntryShown, readEntry, getAddress]);

  return null;
});
