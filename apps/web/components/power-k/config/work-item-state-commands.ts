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
import { getWorkItemPropertyErrorMessage } from "@plane/utils";
// components
import type { TPowerKCommandConfig, TPowerKContext } from "@/components/power-k/core/types";
import { useShortcutWorkItemId } from "@/components/power-k/hooks/use-shortcut-work-item";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useUserPermissions } from "@/hooks/store/user";
import { useIssueStoreType } from "@/hooks/use-issue-layout-store";
import { useIssuesActions } from "@/hooks/use-issues-actions";

/**
 * A state by two keys, S and its letter, for the work item that a shortcut acts on. The change is made as the state
 * chooser of a line of the list makes it, so a list that is grouped by state moves the line at once.
 */
export const usePowerKWorkItemStateCommands = (): TPowerKCommandConfig[] => {
  // store hooks
  const issueDetail = useIssueDetail();
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

  const setState = async (ctx: TPowerKContext, shortcut: TStateShortcut) => {
    const workspaceSlug = ctx.params.workspaceSlug?.toString();
    const workItem = getEditableWorkItem(ctx);
    if (!workspaceSlug || !workItem?.project_id) return;
    const state = getStateOfShortcut(getProjectStates(workItem.project_id) ?? [], shortcut);
    if (!state) {
      setToast({
        type: "info",
        title: t("power_k.contextual_actions.work_item.set_state_toast_no_state", { state: shortcut.names[0] }),
      });
      return;
    }
    if (state.id === workItem.state_id) return;
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

  return STATE_SHORTCUTS.map((shortcut) => ({
    id: `set_work_item_state_${shortcut.id}`,
    i18n_title: `power_k.contextual_actions.work_item.set_state_${shortcut.id}`,
    icon: StateOutline,
    group: "general",
    type: "action",
    keySequence: `s${shortcut.key}`,
    action: (ctx) => setState(ctx, shortcut),
    isEnabled: (ctx) => !!getEditableWorkItem(ctx),
    isVisible: (ctx) => !!getEditableWorkItem(ctx),
    closeOnSelect: true,
  }));
};
