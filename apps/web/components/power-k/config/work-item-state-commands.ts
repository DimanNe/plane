/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { StateOutline } from "@makeplane/propel/icons";
// plane imports
import { getStateOfShortcut, STATE_SHORTCUTS } from "@plane/blocks/state-shortcut";
import type { TStateShortcut } from "@plane/blocks/state-shortcut";
import { setToast } from "@plane/blocks/toast";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { IState, TIssue } from "@plane/types";
import { getWorkItemPropertyErrorMessage } from "@plane/utils";
// components
import { resolveShortcutKey } from "@/components/power-k/core/shortcut-handler";
import type { TPowerKCommandConfig, TPowerKContext } from "@/components/power-k/core/types";
import { useShortcutWorkItemId } from "@/components/power-k/hooks/use-shortcut-work-item";
import { closeStateMenuOfKey } from "@/components/power-k/hooks/use-state-menu-of-key";
import { leavePictureOfChoice, PALETTE_MENU, STATE_SELECT_MENU } from "@/components/power-k/menu-picture";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";
import { usePowerK } from "@/hooks/store/use-power-k";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useUserPermissions } from "@/hooks/store/user";
import { useIssueStoreType } from "@/hooks/use-issue-layout-store";
import { useIssuesActions } from "@/hooks/use-issues-actions";
// store
import type { TStateMenuOfKey } from "@/store/base-power-k.store";

/** Where the key S opens the states of a work item: in its state menu, or on its page in the palette. */
type TStateMenuPlace = TStateMenuOfKey["place"] | "palette";

/**
 * The state of the work item that a shortcut acts on, by keys. S opens the menu of states, and the key after it,
 * the letter of a state, chooses in that menu as a click does. The change is made as the state menu of a line of
 * the list makes it, so a list that is grouped by state moves the line at once.
 */
export const usePowerKWorkItemStateCommands = (): TPowerKCommandConfig[] => {
  // store hooks
  const issueDetail = useIssueDetail();
  const listView = useListView();
  const powerK = usePowerK();
  const { getProjectStates } = useProjectState();
  const { allowPermissions } = useUserPermissions();
  const { updateIssue } = useIssuesActions(useIssueStoreType());
  const getWorkItemId = useShortcutWorkItemId();
  // translation
  const { t } = useTranslation();

  const getEditableWorkItem = (ctx: TPowerKContext) => {
    const workItemId = getWorkItemId(ctx);
    const workItem = workItemId ? issueDetail.issue.getIssueById(workItemId) : undefined;
    const isEditingAllowed =
      !!workItem &&
      !workItem.archived_at &&
      allowPermissions(
        [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
        EUserPermissionsLevel.PROJECT,
        ctx.params.workspaceSlug?.toString(),
        workItem.project_id ?? undefined
      );
    return isEditingAllowed ? workItem : undefined;
  };

  /** The state of the work item's project that the shortcut means; where the project has none, a toast says so. */
  const getStateOfKey = (workItem: TIssue, shortcut: TStateShortcut) => {
    const state = getStateOfShortcut(getProjectStates(workItem.project_id) ?? [], shortcut);
    if (!state)
      setToast({
        type: "info",
        title: t("power_k.contextual_actions.work_item.set_state_toast_no_state", { state: shortcut.names[0] }),
      });
    return state;
  };

  const setState = async (ctx: TPowerKContext, workItem: TIssue, state: IState) => {
    const workspaceSlug = ctx.params.workspaceSlug?.toString();
    if (!workspaceSlug || !workItem.project_id || state.id === workItem.state_id) return;
    try {
      await updateIssue?.(workItem.project_id, workItem.id, { state_id: state.id });
    } catch (error) {
      setToast({
        type: "error",
        title: t("toast.error"),
        message:
          getWorkItemPropertyErrorMessage(error) ??
          t("entity.update.failed", { entity: t("issue.label", { count: 1 }) }),
      });
      return;
    }
    // the peek view and the work item page show the activity of their work item
    if (issueDetail.peekIssue?.issueId === workItem.id || ctx.params.workItem)
      void issueDetail.fetchActivities(workspaceSlug, workItem.project_id, workItem.id);
  };

  /**
   * In the peek view its state menu, on the work item page the palette's page of states, which S has always
   * opened there, and at the selected line of the List layout or of the timeline the state menu of that line.
   * Both draw their lines near the visible part only. A line that is not drawn has no menu: one asked of it would
   * open whenever the line is drawn again.
   */
  const getStateMenuPlace = (ctx: TPowerKContext): TStateMenuPlace | undefined => {
    if (issueDetail.peekIssue) return "peek";
    if (ctx.params.workItem) return "palette";
    const { selectedRow } = listView;
    return selectedRow && document.getElementById(`issue-${selectedRow.issueId}`) ? "list" : undefined;
  };

  /**
   * The key after S, taken before the menu hears it. With the letter of a state the page is the person's again
   * at once: the state is set and the menu closes, and a picture of the menu shows the item of that state for a
   * moment, as it is drawn when it is clicked. Any other key is the menu's, which is an ordinary menu from then on.
   */
  const chooseStateByKey = (
    e: KeyboardEvent,
    ctx: TPowerKContext,
    workItem: TIssue,
    menu: TStateMenuOfKey | "palette"
  ) => {
    const key = e.ctrlKey || e.metaKey || e.altKey || e.shiftKey ? undefined : resolveShortcutKey(e, null);
    const shortcut = STATE_SHORTCUTS.find((stateShortcut) => stateShortcut.key === key);
    const isMenuOpen =
      menu === "palette"
        ? powerK.isPowerKModalOpen && powerK.activePage === "update-work-item-state"
        : powerK.stateMenuOfKey === menu;
    if (!shortcut || !isMenuOpen) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    // without a state for the letter the menu stays, for a choice by hand
    const state = getStateOfKey(workItem, shortcut);
    if (!state) return;
    leavePictureOfChoice(menu === "palette" ? PALETTE_MENU : STATE_SELECT_MENU, state.name);
    if (menu === "palette") ctx.closePalette();
    else closeStateMenuOfKey(powerK);
    const change = setState(ctx, workItem, state);
    // with the list alone the keys go on down the group: the selection does not go away with the line
    if (menu !== "palette" && menu.place === "list") listView.leaveSelectionAtPlaceOf(workItem.id, change);
  };

  const openStateMenu = (ctx: TPowerKContext) => {
    const workItem = getEditableWorkItem(ctx);
    const place = getStateMenuPlace(ctx);
    if (!workItem || !place) return;
    const focused = document.activeElement;
    const focusedBefore = focused instanceof HTMLElement && focused !== document.body ? focused : undefined;
    const menu = place === "palette" ? place : { workItemId: workItem.id, place, focusedBefore };
    if (menu === "palette") {
      powerK.togglePowerKModal(true);
      ctx.setActiveCommand(powerK.commandRegistry.getCommand("change_work_item_state") ?? null);
      ctx.setActivePage("update-work-item-state");
    } else powerK.setStateMenuOfKey(menu);
    // The letter chooses whenever it comes, as long as it is the first key and the menu is still open.
    document.addEventListener("keydown", (e) => chooseStateByKey(e, ctx, workItem, menu), {
      capture: true,
      once: true,
    });
  };

  // A key, not a command of the palette: there the five below are offered, and the work item page has its own
  // command of this name.
  const canOpenStateMenu = (ctx: TPowerKContext) =>
    !powerK.isPowerKModalOpen && !!getStateMenuPlace(ctx) && !!getEditableWorkItem(ctx);

  return [
    {
      id: "open_work_item_state_menu",
      i18n_title: "power_k.contextual_actions.work_item.change_state",
      icon: StateOutline,
      group: "general",
      type: "action",
      shortcut: "s",
      action: openStateMenu,
      isEnabled: canOpenStateMenu,
      isVisible: canOpenStateMenu,
      closeOnSelect: true,
    },
    ...STATE_SHORTCUTS.map(
      (shortcut): TPowerKCommandConfig => ({
        id: `set_work_item_state_${shortcut.id}`,
        i18n_title: `power_k.contextual_actions.work_item.set_state_${shortcut.id}`,
        icon: StateOutline,
        group: "general",
        type: "action",
        keySequence: `s${shortcut.key}`,
        action: (ctx) => {
          const workItem = getEditableWorkItem(ctx);
          const state = workItem && getStateOfKey(workItem, shortcut);
          if (state) void setState(ctx, workItem, state);
        },
        isEnabled: (ctx) => !!getEditableWorkItem(ctx),
        isVisible: (ctx) => !!getEditableWorkItem(ctx),
        closeOnSelect: true,
      })
    ),
  ];
};
