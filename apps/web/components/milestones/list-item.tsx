/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { CalendarOutline, DeleteOutline, EditOutline, MoreHorizontalOutline } from "@makeplane/propel/icons";
import { DateSelect } from "@plane/blocks/property-select";
import { setToast } from "@plane/blocks/toast";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { getDate, renderFormattedPayloadDate } from "@plane/utils";
// components
import { ListItem } from "@/components/core/list";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useUserPermissions, useUserProfile } from "@/hooks/store/user";
import { usePlatformOS } from "@/hooks/use-platform-os";
// local imports
import { MilestoneDeleteModal } from "./delete-modal";
import { MilestoneCreateUpdateModal } from "./milestone-modal";
import { MilestoneProgress, MilestoneStateIcon } from "./progress";

type Props = {
  milestoneId: string;
  workspaceSlug: string;
  projectId: string;
};

export const MilestoneListItem = observer(function MilestoneListItem(props: Props) {
  const { milestoneId, workspaceSlug, projectId } = props;
  // refs
  const parentRef = useRef<HTMLDivElement>(null);
  // states
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  // store hooks
  const { getMilestoneById, updateMilestone } = useMilestone();
  const { allowPermissions } = useUserPermissions();
  const { data: userProfile } = useUserProfile();
  // hooks
  const { isMobile } = usePlatformOS();
  // translation
  const { t } = useTranslation();
  // derived values
  const milestone = getMilestoneById(milestoneId);
  const isEditingAllowed = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );

  if (!milestone) return null;

  const handleTargetDateChange = (date: Date | null) =>
    updateMilestone(workspaceSlug, projectId, milestoneId, {
      target_date: date ? renderFormattedPayloadDate(date) : null,
    }).catch(() =>
      setToast({
        type: "error",
        title: t("toast.error"),
        message: t("common.errors.default.message"),
      })
    );

  return (
    <>
      <MilestoneCreateUpdateModal
        data={milestone}
        isOpen={isUpdateModalOpen}
        handleClose={() => setIsUpdateModalOpen(false)}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
      />
      <MilestoneDeleteModal
        milestone={milestone}
        isOpen={isDeleteModalOpen}
        handleClose={() => setIsDeleteModalOpen(false)}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
      />
      <ListItem
        title={milestone.title}
        itemLink={`/${workspaceSlug}/projects/${projectId}/overview/milestones/${milestone.id}`}
        prependTitleElement={<MilestoneStateIcon milestone={milestone} className="size-4" />}
        actionableItems={
          <>
            <MilestoneProgress milestone={milestone} />
            <DateSelect
              value={getDate(milestone.target_date) ?? null}
              onChange={handleTargetDateChange}
              placeholder={t("target_date")}
              icon={<CalendarOutline />}
              weekStartsOn={userProfile?.start_of_the_week}
              disabled={!isEditingAllowed}
              clearable
              variant="pill-md"
            />
            {isEditingAllowed && (
              <Menu>
                <MenuTrigger
                  render={
                    <IconButton
                      variant="tertiary"
                      size="md"
                      icon={<Icon icon={MoreHorizontalOutline} />}
                      aria-label={t("common.options")}
                    />
                  }
                />
                <MenuContent side="bottom" align="end">
                  <MenuItem
                    icon={<Icon icon={EditOutline} />}
                    label={t("common.actions.edit")}
                    onClick={() => setIsUpdateModalOpen(true)}
                  />
                  <MenuItem
                    variant="danger"
                    icon={<Icon icon={DeleteOutline} />}
                    label={t("common.actions.delete")}
                    onClick={() => setIsDeleteModalOpen(true)}
                  />
                </MenuContent>
              </Menu>
            )}
          </>
        }
        isMobile={isMobile}
        parentRef={parentRef}
      />
    </>
  );
});
