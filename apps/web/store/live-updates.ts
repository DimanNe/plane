/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { compact, isEqual, keyBy, omit, pick, uniq } from "lodash-es";
import { runInAction, when } from "mobx";
import { mutate } from "swr";
// plane imports
import { LIVE_BASE_PATH, LIVE_BASE_URL } from "@plane/constants";
import type { TIssue } from "@plane/types";
// store
import { rootStore } from "@/lib/store-context";
// services
import { IssueService } from "@/services/issue";
import { fetchAroundOwnWrites } from "@/services/own-writes";

/** A changed row as the server reports it: its table and its ids (project, work item), never its content. */
type TChange = { t: string; id: string; p: string | null; i: string | null };
type TMessage = TChange | { resync: true } | { heartbeat: true };
type TList = NonNullable<ReturnType<typeof getListOnScreen>>;
type TOpenIssue = ReturnType<typeof getOpenIssues>[number];

// One change of a work item writes several rows, some of them a moment later in a background task. Changes are
// collected until none has come for the quiet time, and for the maximum time when they keep coming.
const BATCH_QUIET_TIME = 150;
const BATCH_MAX_TIME = 1000;
// The live server sends a heartbeat every 20 seconds. Without any message for this long the connection is dead.
const HEARTBEAT_TIMEOUT = 45_000;
const RECONNECT_DELAY_MIN = 1000;
const RECONNECT_DELAY_MAX = 10_000;
// as many ids as fit the address of one request, beside the filter of the list
const MAX_ISSUES_BY_ID = 30;
// The title and the description of a work item are saved 1.5 seconds after the last key press.
const TYPED_TEXT_SAVE_TIME = 2000;

const issueService = new IssueService();

/**
 * The list of work items on screen. So far only the project's own list is followed, in every layout.
 */
const getListOnScreen = () => {
  const { workspaceSlug, projectId } = rootStore.router;
  const store = rootStore.issue.projectIssues;
  const options = store.paginationOptions;
  // On the other pages of the project the store still holds the list of the last visit.
  const isListPage = window.location.pathname.replace(/\/$/, "").endsWith(`/projects/${projectId}/issues`);
  if (!workspaceSlug || !projectId || !isListPage || !options) return;
  const params = rootStore.issue.projectIssuesFilter.getFilterParams(
    options,
    projectId,
    undefined,
    undefined,
    undefined
  );
  return { workspaceSlug, projectId, store, options, params, listedIssueIds: store.groupedIssueIds };
};

/**
 * Whether the page still shows this list and has not loaded it again since: what it loads itself is newer than
 * an answer that was asked for before. A load replaces the object that holds the ids.
 */
const isStillOnScreen = (list: TList) => {
  const listNow = getListOnScreen();
  return (
    listNow?.projectId === list.projectId &&
    listNow.listedIssueIds === list.listedIssueIds &&
    isEqual(listNow.params, list.params)
  );
};

/**
 * The work items that are open: in the view beside a list, and on a page of their own. `close` is for one that
 * exists no more.
 */
const getOpenIssues = () => {
  const { router, issue } = rootStore;
  const { peekIssue } = issue.issueDetail;
  const issueOfPage = issue.issues.getIssueById(
    issue.issues.getIssueIdByIdentifier(String(router.query.workItem)) ?? ""
  );
  return compact([
    peekIssue && !peekIssue.isArchived && { ...peekIssue, close: () => issue.issueDetail.setPeekIssue(undefined) },
    router.workspaceSlug &&
      issueOfPage?.project_id && {
        workspaceSlug: router.workspaceSlug,
        projectId: issueOfPage.project_id,
        issueId: issueOfPage.id,
        // the page fetches the work item itself then, and says that it does not exist
        close: () => void mutate((key) => typeof key === "string" && key.startsWith("ISSUE_DETAIL_")),
      },
  ]);
};

const isTextFieldFocused = () => {
  const element = document.activeElement;
  return element instanceof HTMLElement && (element.isContentEditable || element.matches("input, textarea"));
};

/**
 * Keeps an open page in step with what others change: another person, an agent through the API, a background
 * task. The live server sends the ids of every changed row of the workspace. The page fetches what it shows of
 * them and merges it into its stores; a row it has no rule for is ignored.
 */
export class LiveUpdates {
  private socket: WebSocket | undefined;
  private reconnectDelay = RECONNECT_DELAY_MIN;
  // runs `connect`: after the delay when the connection was closed, after the heartbeat timeout while it is open
  private connectTimer: ReturnType<typeof setTimeout> | undefined;
  private batchQuietTimer: ReturnType<typeof setTimeout> | undefined;
  private batchMaxTimer: ReturnType<typeof setTimeout> | undefined;
  private typedTextTimer: ReturnType<typeof setTimeout> | undefined;
  private isTypedTextKept = false;
  private changes: TChange[] = [];
  private isResyncPending = false;
  private applying = Promise.resolve();

  constructor(private readonly workspaceSlug: string) {
    this.connect();
    document.addEventListener("focusout", this.refetchAfterTyping);
  }

  stop() {
    document.removeEventListener("focusout", this.refetchAfterTyping);
    [this.connectTimer, this.batchQuietTimer, this.batchMaxTimer, this.typedTextTimer].forEach(clearTimeout);
    const socket = this.socket;
    this.socket = undefined;
    socket?.close();
  }

  private connect = () => {
    this.socket?.close();
    const url = new URL(LIVE_BASE_URL?.trim() || window.location.origin);
    url.protocol = window.location.protocol === "https:" ? "wss" : "ws";
    url.pathname = `${LIVE_BASE_PATH}/events`;
    url.searchParams.set("workspaceSlug", this.workspaceSlug);
    const socket = new WebSocket(url);
    this.socket = socket;
    socket.addEventListener("message", (event) => {
      if (socket !== this.socket) return;
      this.reconnectDelay = RECONNECT_DELAY_MIN;
      this.connectTimer = this.restart(this.connectTimer, this.connect, HEARTBEAT_TIMEOUT);
      this.receive(JSON.parse(event.data));
    });
    socket.addEventListener("close", () => {
      if (socket !== this.socket) return;
      this.connectTimer = this.restart(this.connectTimer, this.connect, this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_DELAY_MAX);
    });
    this.connectTimer = this.restart(this.connectTimer, this.connect, HEARTBEAT_TIMEOUT);
  };

  private restart(timer: ReturnType<typeof setTimeout> | undefined, run: () => void, delay: number) {
    clearTimeout(timer);
    return setTimeout(run, delay);
  }

  private receive(message: TMessage) {
    if ("resync" in message) {
      // Changes may have been missed, on the first connection too: between the load of the page and this message.
      this.isResyncPending = true;
      this.apply();
    } else if ("t" in message) {
      this.changes.push(message);
      this.batchQuietTimer = this.restart(this.batchQuietTimer, this.apply, BATCH_QUIET_TIME);
      this.batchMaxTimer ??= setTimeout(this.apply, BATCH_MAX_TIME);
    }
  }

  // One batch after the other, so that an older answer of the server is never applied after a newer one.
  private apply = () => {
    [this.batchQuietTimer, this.batchMaxTimer].forEach(clearTimeout);
    this.batchMaxTimer = undefined;
    this.applying = this.applying
      .then(async () => {
        // A list that the page is loading itself may come back older than these changes: they are applied to it.
        // An operation on a timeline works on a copy of the plan: what changed elsewhere waits until it has ended.
        const { schedule } = rootStore.timelineStore.issuesTimeLineStore;
        await when(() => !rootStore.issue.projectIssues.getIssueLoader() && !schedule.operation);
        const changes = this.changes.splice(0);
        const isResync = this.isResyncPending;
        this.isResyncPending = false;
        return isResync ? this.refetch() : this.applyChanges(changes);
      })
      // A failed fetch is not made again: the next change or the next connection brings the page up to date.
      .catch((error) => console.error("Live updates: failed to fetch what changed", error));
  };

  private async refetch() {
    const list = getListOnScreen();
    if (list) await this.refetchList(list);
    await Promise.all(getOpenIssues().map((openIssue) => this.refetchOpenIssue(openIssue)));
    await this.refetchPlans();
  }

  private async applyChanges(changes: TChange[]) {
    // the changed work items of a project: a row of a work item names it in `i`
    const getIssueIds = (projectId: string) =>
      uniq(
        compact(
          changes
            .filter((change) => change.p === projectId)
            .map((change) => (change.t === "issues" ? change.id : change.i))
        )
      );
    const list = getListOnScreen();
    const listIssueIds = list ? getIssueIds(list.projectId) : [];
    if (list && listIssueIds.length > 0) await this.applyToList(list, listIssueIds);
    await Promise.all(
      getOpenIssues().map((openIssue) => this.applyToOpenIssue(openIssue, getIssueIds(openIssue.projectId)))
    );
    await this.refetchPlans(changes);
  }

  /**
   * Rule for the plan of a timeline: a change of a record that the plan of a project is computed from fetches
   * the project's dependencies and the work items at their ends again, whatever it was that changed of them.
   * This goes for every project whose timeline the page has loaded, on screen or not: a timeline that is shown
   * again does not ask the server again. The store then saves computed dates that differ from the stored ones,
   * as when a timeline loads; that save comes back as a change, whose fetch finds nothing left to save.
   * Without `changes` every plan is fetched: nobody knows what was missed.
   */
  private async refetchPlans(changes?: TChange[]) {
    const { schedule, fetchDependencies } = rootStore.timelineStore.issuesTimeLineStore;
    const projectIds = schedule
      .getHeldProjectIds(this.workspaceSlug)
      .filter(
        (projectId) => !changes || changes.some((change) => schedule.isPlanComputedFrom(projectId, change.t, change.id))
      );
    await Promise.all(projectIds.map((projectId) => fetchDependencies(this.workspaceSlug, projectId)));
  }

  /**
   * Rule for a list: the changed work items are asked for by id with the filter of the list. What the server
   * returns is in the list in its new state, what it does not return is not in the list (any more): deleted,
   * archived, or changed so that the filter leaves it out.
   */
  private async applyToList(list: TList, issueIds: string[]): Promise<void> {
    const { workspaceSlug, projectId, store, params } = list;
    // The list of the timeline also carries the relations of its work items, which only the list request returns.
    if (params.expand || issueIds.length > MAX_ISSUES_BY_ID) return this.refetchList(list);
    const issues = await fetchAroundOwnWrites(() =>
      issueService.retrieveIssues(
        workspaceSlug,
        projectId,
        issueIds,
        omit(params, ["group_by", "sub_group_by", "cursor", "per_page"])
      )
    );
    if (!isStillOnScreen(list)) return;
    const issuesById = keyBy(issues, "id");
    const issuesMap = rootStore.issue.issues.issuesMap;
    const parentIds: string[] = [];
    runInAction(() => {
      for (const issueId of issueIds) {
        const parentIdBefore = issuesMap[issueId]?.parent_id;
        const parentId = issuesById[issueId]?.parent_id;
        if (this.isRowTitleTyped(projectId, issueId)) continue;
        if (parentIdBefore !== parentId) parentIds.push(...compact([parentIdBefore, parentId]));
        const issue = issuesById[issueId];
        store.applyIssueFromServer(
          issueId,
          issue && { ...issue, ...pick(issuesMap[issueId], this.getKeptFields(issueId)) }
        );
      }
    });
    // A work item got or lost a parent: the number of sub-work items of a parent is the server's to count.
    const staleParentIds = uniq(parentIds).filter((id) => issuesMap[id] && !issueIds.includes(id));
    const listNow = getListOnScreen();
    if (listNow && staleParentIds.length > 0) await this.applyToList(listNow, staleParentIds);
  }

  /**
   * The whole list is fetched: after a lost connection nobody knows what was missed. It replaces the shown one in
   * one step. A fetch of the page itself clears the list first, and the layout would show its loading skeleton.
   */
  private async refetchList(list: TList) {
    const { workspaceSlug, projectId, store, options, params } = list;
    const response = await fetchAroundOwnWrites(() => issueService.getIssues(workspaceSlug, projectId, params));
    if (isStillOnScreen(list)) store.onfetchIssues(response, options, workspaceSlug, projectId, undefined, false);
  }

  /**
   * Rule for an open work item: a change that names it fetches all of it again, its fields and description, its
   * comments, activity, sub-work items and relations. A change of another work item of its project fetches its
   * sub-work items: the other one may be one of them, have become one, or have stopped being one.
   */
  private async applyToOpenIssue(openIssue: TOpenIssue, issueIds: string[]) {
    const { workspaceSlug, projectId, issueId } = openIssue;
    if (issueIds.includes(issueId)) await this.refetchOpenIssue(openIssue);
    else if (issueIds.length > 0)
      await rootStore.issue.issueDetail.subIssues.fetchSubIssues(workspaceSlug, projectId, issueId);
  }

  private async refetchOpenIssue({ workspaceSlug, projectId, issueId, close }: TOpenIssue) {
    const { issueDetail } = rootStore.issue;
    try {
      // The store applies the answer itself, also one that crossed a write of the page: it is fetched again then.
      await fetchAroundOwnWrites(() =>
        issueDetail.issue.fetchIssue(workspaceSlug, projectId, issueId, this.getKeptFields(issueId))
      );
    } catch {
      // It was deleted or archived when the server does not list it either. Any other failure leaves it open.
      const issues = await issueService.retrieveIssues(workspaceSlug, projectId, [issueId]);
      if (issues.length === 0) close();
    }
  }

  /**
   * Rule for typed text: while a text field has the focus, the name and the description of an open work item
   * stay as they are on the page, and everything else of it follows. The typed text is saved over what was
   * changed elsewhere.
   */
  private getKeptFields(issueId: string): (keyof TIssue)[] {
    if (!isTextFieldFocused() || !getOpenIssues().some((openIssue) => openIssue.issueId === issueId)) return [];
    this.isTypedTextKept = true;
    return ["name", "description_html"];
  }

  /**
   * Typed text in a row of the list: a row that moves to another group is made anew there and would lose the
   * title being typed in it. The work item is left as it is on the page until the typing has ended.
   */
  private isRowTitleTyped(projectId: string, issueId: string) {
    const { issueListView } = rootStore.issue;
    if (!issueListView.selectedRow?.isEditing || issueListView.selectedRow.issueId !== issueId) return false;
    void when(() => !issueListView.selectedRow?.isEditing).then(() => {
      this.changes.push({ t: "issues", id: issueId, p: projectId, i: null });
      return this.apply();
    });
    return true;
  }

  // The focus has left the text field: once the typed text is saved, what was kept back is fetched.
  private refetchAfterTyping = () => {
    if (!this.isTypedTextKept) return;
    this.typedTextTimer = this.restart(
      this.typedTextTimer,
      () => {
        this.isTypedTextKept = false;
        this.changes.push(
          ...getOpenIssues().map(({ projectId, issueId }) => ({ t: "issues", id: issueId, p: projectId, i: null }))
        );
        this.apply();
      },
      TYPED_TEXT_SAVE_TIME
    );
  };
}
