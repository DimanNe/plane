/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { ArrowDownOutline, DeleteOutline, DueDateOutline, StartDateOutline } from "@makeplane/propel/icons";
import { Select } from "@plane/blocks/select";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TTimelineDependency, TTimelineDependencyTypes } from "@plane/types";
import { renderFormattedDate } from "@plane/utils";
// components
import { IssueIdentifier } from "@/components/issues/issue-detail/issue-identifier";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";

const DEPENDENCY_TYPES: TTimelineDependencyTypes[] = ["blocking", "start_before", "finish_before"];

export type TTimelineRelation = {
  predecessorId: string;
  dependentId: string;
  /** The saved dependency; absent while the connector was just dropped and the type is still to be chosen. */
  dependency?: TTimelineDependency;
};

type Props = {
  relation: TTimelineRelation;
  isEditable: boolean;
  handleClose: () => void;
};

const TimelineRelationWorkItem = observer(function TimelineRelationWorkItem(props: { issueId: string }) {
  const { issueId } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // derived values
  const issue = getIssueById(issueId);

  if (!issue?.project_id) return null;

  return (
    <div className="flex items-center gap-2 rounded-md border border-subtle px-3 py-2.5 text-body-xs-regular">
      <IssueIdentifier issueId={issue.id} projectId={issue.project_id} size="xs" variant="tertiary" />
      <span className="grow truncate text-body-xs-medium text-primary">{issue.name}</span>
      <span className="flex shrink-0 items-center gap-1 text-secondary">
        <StartDateOutline className="size-3.5" />
        {renderFormattedDate(issue.start_date)}
        <span>-</span>
        <DueDateOutline className="size-3.5" />
        {renderFormattedDate(issue.target_date)}
      </span>
    </div>
  );
});

export const TimelineRelationModal = observer(function TimelineRelationModal(props: Props) {
  const { relation, isEditable, handleClose } = props;
  const { predecessorId, dependentId, dependency } = relation;
  // router
  const { workspaceSlug, projectId } = useParams();
  // states
  const [relationType, setRelationType] = useState<TTimelineDependencyTypes>(dependency?.relation_type ?? "blocking");
  const [isSubmitting, setIsSubmitting] = useState(false);
  // store hooks
  const { createRelation, removeRelation } = useIssueDetail();
  // translation
  const { t } = useTranslation();

  const handleSubmit = async (action: Promise<unknown>) => {
    setIsSubmitting(true);
    await action
      .then(() => handleClose())
      .catch((error) =>
        setToast({
          type: "error",
          title: t("toast.error"),
          message: error?.error ?? t("common.errors.default.message"),
        })
      )
      .finally(() => setIsSubmitting(false));
  };

  // a dependency is a relation of the predecessor; the relation store refreshes the lines of the timeline
  const handleCreate = () =>
    handleSubmit(
      createRelation(workspaceSlug.toString(), projectId.toString(), predecessorId, relationType, [dependentId])
    );

  const handleRemove = (savedDependency: TTimelineDependency) =>
    handleSubmit(
      removeRelation(
        workspaceSlug.toString(),
        projectId.toString(),
        predecessorId,
        savedDependency.relation_type,
        dependentId
      )
    );

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent size="md">
        <DialogMain>
          <DialogHeader>
            <DialogHeading>
              <DialogTitle>{t("timeline_dependency.title")}</DialogTitle>
            </DialogHeading>
          </DialogHeader>
          <DialogBody>
            <TimelineRelationWorkItem issueId={predecessorId} />
            <div className="flex items-center gap-2 py-2 pl-3 text-accent-primary">
              <ArrowDownOutline className="size-4 shrink-0" />
              {dependency ? (
                <>
                  <span className="grow text-body-xs-medium">{t(`issue.relation.${dependency.relation_type}`)}</span>
                  {isEditable && (
                    <IconButton
                      variant="ghost"
                      size="md"
                      icon={<Icon icon={DeleteOutline} />}
                      aria-label={t("common.remove")}
                      disabled={isSubmitting}
                      onClick={() => handleRemove(dependency)}
                    />
                  )}
                </>
              ) : (
                <Select<TTimelineDependencyTypes>
                  getValues={() => DEPENDENCY_TYPES}
                  value={relationType}
                  onChange={(value) => setRelationType(value as TTimelineDependencyTypes)}
                  showSearch={false}
                  pinSelected={false}
                  getOptionValue={(option) => option}
                  getOptionLabel={(option) => t(`issue.relation.${option}`)}
                >
                  <Select.Trigger<TTimelineDependencyTypes> variant="select-md">
                    {(selected) => (
                      <span className="grow truncate text-left">{t(`issue.relation.${selected[0]}`)}</span>
                    )}
                  </Select.Trigger>
                </Select>
              )}
            </div>
            <TimelineRelationWorkItem issueId={dependentId} />
          </DialogBody>
        </DialogMain>
        {!dependency && (
          <DialogActions>
            <Button variant="secondary" size="md" stretch="auto" label={t("common.cancel")} onClick={handleClose} />
            <Button
              variant="primary"
              size="md"
              stretch="auto"
              label={t("issue.add.dependency")}
              loading={isSubmitting}
              onClick={handleCreate}
            />
          </DialogActions>
        )}
      </DialogContent>
    </Dialog>
  );
});
