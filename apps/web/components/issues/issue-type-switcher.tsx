/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { SwitchHorizontalOutline } from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
// store hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// components
import { IssueIdentifier } from "@/components/issues/issue-detail/issue-identifier";
import { CreateUpdateIssueModal } from "@/components/issues/issue-modal/modal";

export type TIssueTypeSwitcherProps = {
  issueId: string;
  disabled: boolean;
};

export const IssueTypeSwitcher = observer(function IssueTypeSwitcher(props: TIssueTypeSwitcherProps) {
  const { issueId, disabled } = props;
  // states
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getProjectWorkItemTypes } = useWorkItemTypes();
  // derived values
  const issue = getIssueById(issueId);

  if (!issue || !issue.project_id) return <></>;

  const canSwitchType = !disabled && !!getProjectWorkItemTypes(issue.project_id)?.length;

  return (
    <div className="group/type-switcher flex items-center gap-2">
      <IssueIdentifier issueId={issueId} projectId={issue.project_id} size="md" enableClickToCopyIdentifier />
      {/* the type is one of the fields of the update modal, where its properties can be filled in */}
      {canSwitchType && (
        <div className="opacity-0 transition-opacity group-hover/type-switcher:opacity-100 focus-within:opacity-100">
          <Button
            variant="ghost"
            size="sm"
            stretch="auto"
            icon={<Icon icon={SwitchHorizontalOutline} />}
            label={t("work_item_types.change_confirmation.switch")}
            onClick={() => setIsUpdateModalOpen(true)}
          />
        </div>
      )}
      <CreateUpdateIssueModal isOpen={isUpdateModalOpen} onClose={() => setIsUpdateModalOpen(false)} data={issue} />
    </div>
  );
});
