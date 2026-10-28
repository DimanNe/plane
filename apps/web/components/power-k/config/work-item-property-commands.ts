/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { PriorityOutline, StateOutline } from "@makeplane/propel/icons";
// plane imports
import { getStateOfKey, getStateOfShortcut, STATE_SHORTCUTS } from "@plane/blocks/state-shortcut";
import type { TStateShortcut } from "@plane/blocks/state-shortcut";
import { setToast } from "@plane/blocks/toast";
import { EUserPermissions, EUserPermissionsLevel, ISSUE_PRIORITIES } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TIssue } from "@plane/types";
import { getWorkItemPropertyErrorMessage } from "@plane/utils";
// components
import { KEY_SEQUENCE_TIMEOUT_MS, resolveShortcutKey } from "@/components/power-k/core/shortcut-handler";
import type { TPowerKCommandConfig, TPowerKContext, TPowerKPageType } from "@/components/power-k/core/types";
import { closePropertyMenuOfKey } from "@/components/power-k/hooks/use-property-menu-of-key";
import { useShortcutWorkItemId } from "@/components/power-k/hooks/use-shortcut-work-item";
import { leavePictureOfChoice, PALETTE_MENU, PROPERTY_MENU } from "@/components/power-k/menu-picture";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useListView } from "@/hooks/store/use-list-view";
import { usePowerK } from "@/hooks/store/use-power-k";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useUserPermissions } from "@/hooks/store/user";
import { useIssueStoreType } from "@/hooks/use-issue-layout-store";
import { useIssuesActions } from "@/hooks/use-issues-actions";
// store
import type { TPropertyMenuOfKey } from "@/store/base-power-k.store";

/**
 * The key after P: the first letter of a priority's name. The letters are those of the English names, which are the
 * priorities' keys too, so they are the same in every language: P U, P H, P M, P L and P N.
 */
const PRIORITY_SHORTCUTS = ISSUE_PRIORITIES.map(({ key: priority, title }) => ({
  priority,
  title,
  key: priority.charAt(0),
}));

/** Where a key opens the menu of a property of a work item: in that menu, or on its page in the palette. */
type TPropertyMenuPlace = TPropertyMenuOfKey["place"] | "palette";

/**
 * What the key of a property opened for the key after it: a menu of the property, the palette's page of it, or
 * nothing, where the selected line is not drawn or does not show the property, and so has no menu (see
 * getPropertyMenuPlace).
 */
type TPropertyMenuOfThisKey = TPropertyMenuOfKey | "palette" | "no menu";

/** What the key after the key of a property chooses: the change to store, and the text of its item in the menu. */
type TChoiceOfKey = { change: Partial<TIssue>; itemText: string };

/**
 * A property whose menu a key opens, and in whose menu the key after it chooses as a click does: S for the state,
 * with the first letter of a state (see getStateOfKey), and P for the priority, with the first letter of a priority.
 */
type TPropertyOfKey = {
  property: TPropertyMenuOfKey["property"];
  key: string;
  i18nTitle: string;
  icon: TPowerKCommandConfig["icon"];
  /** The control of the property on a line of the list, where the menu of that line opens. */
  lineControl: string;
  /** The palette's command and page of the property, which its key has always opened on the work item page. */
  paletteCommandId: string;
  palettePage: TPowerKPageType;
  /**
   * What the key after the property's key means for the work item. Undefined: the key is the menu's, as typing is
   * in the search of the menu of states. "said": the key means nothing in this project, and a message has said so.
   */
  getChoiceOfKey: (workItem: TIssue, key: string, isPalette: boolean) => TChoiceOfKey | "said" | undefined;
};

/**
 * The state and the priority of the work item that a shortcut acts on, by keys. S or P opens the menu of the
 * property, and the key after it chooses in that menu as a click does. The change is made as the menu of a line of
 * the list makes it, so a list that is grouped by that property moves the line at once.
 */
export const usePowerKWorkItemPropertyCommands = (): TPowerKCommandConfig[] => {
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

  /** Says that the work item's project has no state that the shortcut means. */
  const showNoStateOfShortcut = (shortcut: TStateShortcut) =>
    setToast({
      type: "info",
      title: t("power_k.contextual_actions.work_item.set_state_toast_no_state", { state: shortcut.names[0] }),
    });

  /** The state of the work item's project that the shortcut means; where the project has none, a toast says so. */
  const getStateOfShortcutOrShowNone = (workItem: TIssue, shortcut: TStateShortcut) => {
    const state = getStateOfShortcut(getProjectStates(workItem.project_id) ?? [], shortcut);
    if (!state) showNoStateOfShortcut(shortcut);
    return state;
  };

  /** Stores the change, unless the work item has it already. */
  const updateWorkItem = async (ctx: TPowerKContext, workItem: TIssue, change: Partial<TIssue>) => {
    const workspaceSlug = ctx.params.workspaceSlug?.toString();
    const isChanged = Object.entries(change).some(([field, value]) => workItem[field as keyof TIssue] !== value);
    if (!workspaceSlug || !workItem.project_id || !isChanged) return;
    try {
      await updateIssue?.(workItem.project_id, workItem.id, change);
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
   * In the peek view the property's menu, on the work item page the palette's page of the property, which its key
   * has always opened there, and at the selected line of the List layout or of the timeline the property's menu of
   * that line. Both draw their lines near the visible part only, and a line of the list shows its priority only
   * while Display shows priorities. A line that is not drawn, or does not show the property, has no menu: one asked
   * of it would open whenever the line draws the property again.
   */
  const getPropertyMenuPlace = (ctx: TPowerKContext, propertyOfKey: TPropertyOfKey): TPropertyMenuPlace | undefined => {
    if (issueDetail.peekIssue) return "peek";
    if (ctx.params.workItem) return "palette";
    const { selectedRow } = listView;
    const line = selectedRow && document.getElementById(`issue-${selectedRow.issueId}`);
    return line?.querySelector(propertyOfKey.lineControl) ? "list" : undefined;
  };

  /**
   * The key after the property's key, taken before the menu hears it. With the letter of a value the page is the
   * person's again at once: the value is set and the menu closes, and a picture of the menu shows the item of that
   * value for a moment, as it is drawn when it is clicked. Any other key is the menu's, which is an ordinary menu
   * from then on: typing searches the menu of states.
   */
  const chooseByKey = (
    e: KeyboardEvent,
    ctx: TPowerKContext,
    workItem: TIssue,
    menu: TPropertyMenuOfThisKey,
    propertyOfKey: TPropertyOfKey
  ) => {
    const key = e.ctrlKey || e.metaKey || e.altKey || e.shiftKey ? undefined : resolveShortcutKey(e, null);
    const isMenuOpen =
      menu === "no menu" ||
      (menu === "palette"
        ? powerK.isPowerKModalOpen && powerK.activePage === propertyOfKey.palettePage
        : powerK.propertyMenuOfKey === menu);
    // a named key (Escape, the arrows, Enter) is the menu's; the space is "space"
    if (!key || key.length !== 1 || !isMenuOpen) return;
    const choice = propertyOfKey.getChoiceOfKey(workItem, key, menu === "palette");
    if (!choice) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    // the menu stays for a choice by hand
    if (choice === "said") return;
    if (menu !== "no menu") leavePictureOfChoice(menu === "palette" ? PALETTE_MENU : PROPERTY_MENU, choice.itemText);
    if (menu === "palette") ctx.closePalette();
    else if (menu !== "no menu") closePropertyMenuOfKey(powerK);
    const change = updateWorkItem(ctx, workItem, choice.change);
    // with the list alone the keys go on down the group: the selection does not go away with the line
    if (menu === "no menu" || (menu !== "palette" && menu.place === "list"))
      listView.leaveSelectionAtPlaceOf(workItem.id, change);
  };

  const openPropertyMenu = (ctx: TPowerKContext, propertyOfKey: TPropertyOfKey) => {
    const workItem = getEditableWorkItem(ctx);
    if (!workItem) return;
    const place = getPropertyMenuPlace(ctx, propertyOfKey);
    if (!place) {
      // The selected line has no menu of the property, so nothing opens, and the key after the property's key is
      // taken as the second key of a sequence is: within the time a sequence waits for it.
      const chooseWithoutMenu = (e: KeyboardEvent) => chooseByKey(e, ctx, workItem, "no menu", propertyOfKey);
      document.addEventListener("keydown", chooseWithoutMenu, { capture: true, once: true });
      window.setTimeout(
        () => document.removeEventListener("keydown", chooseWithoutMenu, { capture: true }),
        KEY_SEQUENCE_TIMEOUT_MS
      );
      return;
    }
    const focused = document.activeElement;
    const focusedBefore = focused instanceof HTMLElement && focused !== document.body ? focused : undefined;
    const menu =
      place === "palette" ? place : { property: propertyOfKey.property, workItemId: workItem.id, place, focusedBefore };
    if (menu === "palette") {
      powerK.togglePowerKModal(true);
      ctx.setActiveCommand(powerK.commandRegistry.getCommand(propertyOfKey.paletteCommandId) ?? null);
      ctx.setActivePage(propertyOfKey.palettePage);
    } else powerK.setPropertyMenuOfKey(menu);
    // The letter chooses whenever it comes, as long as it is the first key and the menu is still open.
    document.addEventListener("keydown", (e) => chooseByKey(e, ctx, workItem, menu, propertyOfKey), {
      capture: true,
      once: true,
    });
  };

  // A key, not a command of the palette: there the sequences below are offered, and the work item page has its own
  // command of this name.
  const canChooseByKey = (ctx: TPowerKContext) => !powerK.isPowerKModalOpen && !!getEditableWorkItem(ctx);

  const getOpenPropertyMenuCommand = (propertyOfKey: TPropertyOfKey): TPowerKCommandConfig => ({
    id: `open_work_item_${propertyOfKey.property}_menu`,
    i18n_title: propertyOfKey.i18nTitle,
    icon: propertyOfKey.icon,
    group: "general",
    type: "action",
    shortcut: propertyOfKey.key,
    action: (ctx) => openPropertyMenu(ctx, propertyOfKey),
    isEnabled: canChooseByKey,
    isVisible: canChooseByKey,
    closeOnSelect: true,
  });

  const stateOfKey: TPropertyOfKey = {
    property: "state",
    key: "s",
    i18nTitle: "power_k.contextual_actions.work_item.change_state",
    icon: StateOutline,
    lineControl: '[data-filter-property="state_id"]',
    paletteCommandId: "change_work_item_state",
    palettePage: "update-work-item-state",
    getChoiceOfKey: (workItem, key) => {
      const state = getStateOfKey(getProjectStates(workItem.project_id) ?? [], key);
      if (state) return { change: { state_id: state.id }, itemText: state.name };
      // A letter of STATE_SHORTCUTS that the project has no state for says so, and the menu stays for a choice by
      // hand; any other key without a state is typed into the menu's search.
      const shortcut = STATE_SHORTCUTS.find((stateShortcut) => stateShortcut.key === key);
      if (!shortcut) return undefined;
      showNoStateOfShortcut(shortcut);
      return "said";
    },
  };

  const priorityOfKey: TPropertyOfKey = {
    property: "priority",
    key: "p",
    i18nTitle: "power_k.contextual_actions.work_item.change_priority",
    icon: PriorityOutline,
    lineControl: '[data-filter-property="priority"]',
    paletteCommandId: "change_work_item_priority",
    palettePage: "update-work-item-priority",
    // Every project has every priority. The menu of priorities has no search, so any other key is left to it.
    getChoiceOfKey: (_workItem, key, isPalette) => {
      // FOR_REVIEWER: the letters are the English initials in every language. With the initials of the names that
      // the menu shows in the person's language, P M would be another key in other languages, and two priorities
      // could share one. A list whose Display hides priorities draws no menu at its line: there P and the letter
      // set the priority without one, within the time a key sequence waits, as S does on a line that is not drawn.
      const shortcut = PRIORITY_SHORTCUTS.find((priorityShortcut) => priorityShortcut.key === key);
      if (!shortcut) return undefined;
      // the palette names a priority by its title, the menu as @plane/blocks' PrioritySelect does
      const itemText = isPalette ? shortcut.title : t(shortcut.priority) || shortcut.title;
      return { change: { priority: shortcut.priority }, itemText };
    },
  };

  return [
    getOpenPropertyMenuCommand(stateOfKey),
    // From the keyboard S and P take the key after them themselves (chooseByKey), so these sequences are what the
    // palette and the list of shortcuts show.
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
          const state = workItem && getStateOfShortcutOrShowNone(workItem, shortcut);
          if (state) void updateWorkItem(ctx, workItem, { state_id: state.id });
        },
        isEnabled: (ctx) => !!getEditableWorkItem(ctx),
        isVisible: (ctx) => !!getEditableWorkItem(ctx),
        closeOnSelect: true,
      })
    ),
    getOpenPropertyMenuCommand(priorityOfKey),
    ...PRIORITY_SHORTCUTS.map(
      (shortcut): TPowerKCommandConfig => ({
        id: `set_work_item_priority_${shortcut.priority}`,
        i18n_title: `power_k.contextual_actions.work_item.set_priority_${shortcut.priority}`,
        icon: PriorityOutline,
        group: "general",
        type: "action",
        keySequence: `p${shortcut.key}`,
        action: (ctx) => {
          const workItem = getEditableWorkItem(ctx);
          if (workItem) void updateWorkItem(ctx, workItem, { priority: shortcut.priority });
        },
        isEnabled: (ctx) => !!getEditableWorkItem(ctx),
        isVisible: (ctx) => !!getEditableWorkItem(ctx),
        closeOnSelect: true,
      })
    ),
  ];
};
