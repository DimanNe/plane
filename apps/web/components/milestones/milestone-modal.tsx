/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Controller, useForm } from "react-hook-form";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { Dialog, DialogContent } from "@makeplane/propel/components/dialog";
import { Field } from "@makeplane/propel/components/field";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { CalendarOutline } from "@makeplane/propel/icons";
import { DateSelect } from "@plane/blocks/property-select";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TMilestone } from "@plane/types";
import { getDate, renderFormattedPayloadDate } from "@plane/utils";
// components
import { RichTextEditor } from "@/components/editor/rich-text";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserProfile } from "@/hooks/store/user";
// services
import { WorkspaceService } from "@/services/workspace.service";

type Props = {
  isOpen: boolean;
  handleClose: () => void;
  data?: TMilestone;
  workspaceSlug: string;
  projectId: string;
};

type TMilestoneFormValues = Pick<TMilestone, "title" | "description_html" | "target_date">;

const workspaceService = new WorkspaceService();

const MilestoneForm = observer(function MilestoneForm(props: Omit<Props, "isOpen">) {
  const { handleClose, data, workspaceSlug, projectId } = props;
  // store hooks
  const { createMilestone, updateMilestone } = useMilestone();
  const { getWorkspaceBySlug } = useWorkspace();
  const { data: userProfile } = useUserProfile();
  // translation
  const { t } = useTranslation();
  // form data
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    control,
  } = useForm<TMilestoneFormValues>({
    defaultValues: {
      title: data?.title ?? "",
      description_html: data?.description_html ?? "<p></p>",
      target_date: data?.target_date ?? null,
    },
  });
  // derived values
  const workspaceId = getWorkspaceBySlug(workspaceSlug)?.id;

  const handleFormSubmit = async (formData: TMilestoneFormValues) => {
    try {
      if (data) await updateMilestone(workspaceSlug, projectId, data.id, formData);
      else await createMilestone(workspaceSlug, projectId, formData);
      setToast({
        type: "success",
        title: t("toast.success"),
        message: t(data ? "project_milestones.toast.updated" : "project_milestones.toast.created"),
      });
      handleClose();
    } catch (error) {
      // the server answers with the reason per field, as for a title that is already used in the project
      setToast({
        type: "error",
        title: t("toast.error"),
        message: (error as { title?: string[] })?.title?.[0] ?? t("common.errors.default.message"),
      });
    }
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)}>
      <div className="space-y-5 p-5">
        <h3 className="text-18 font-medium text-secondary">
          {data ? t("project_milestones.update_milestone") : t("project_milestones.create_milestone")}
        </h3>
        <div className="space-y-3">
          <div className="space-y-1">
            <Controller
              name="title"
              control={control}
              rules={{
                required: t("title_is_required"),
                maxLength: { value: 255, message: t("title_should_be_less_than_255_characters") },
              }}
              render={({ field: { value, onChange } }) => (
                <Field name="title" invalid={Boolean(errors?.title)}>
                  <InputGroup size="2xl">
                    <Input
                      size="2xl"
                      name="title"
                      type="text"
                      placeholder={t("title")}
                      value={value}
                      onChange={onChange}
                      // oxlint-disable-next-line jsx_a11y/no-autofocus
                      autoFocus
                      aria-label={t("title")}
                    />
                  </InputGroup>
                </Field>
              )}
            />
            <span className="text-11 text-danger-primary">{errors?.title?.message}</span>
          </div>
          {workspaceId && (
            <Controller
              name="description_html"
              control={control}
              render={({ field: { value, onChange } }) => (
                <div className="rounded-md border-[0.5px] border-subtle">
                  <RichTextEditor
                    editable
                    id="milestone-modal-editor"
                    initialValue={value}
                    workspaceSlug={workspaceSlug}
                    workspaceId={workspaceId}
                    projectId={projectId}
                    onChange={(_description: object, description_html: string) => onChange(description_html)}
                    placeholder={t("description")}
                    searchMentionCallback={async (payload) =>
                      await workspaceService.searchEntity(workspaceSlug, { ...payload, project_id: projectId })
                    }
                    containerClassName="min-h-[120px] pt-3"
                    // a milestone has no asset entity on the server, so its description takes no images
                    disabledExtensions={["image"]}
                    uploadFile={async () => ""}
                    duplicateFile={async () => ""}
                  />
                </div>
              )}
            />
          )}
          <Controller
            name="target_date"
            control={control}
            render={({ field: { value, onChange } }) => (
              <DateSelect
                value={getDate(value) ?? null}
                onChange={(date) => onChange(date ? renderFormattedPayloadDate(date) : null)}
                placeholder={t("target_date")}
                icon={<CalendarOutline />}
                weekStartsOn={userProfile?.start_of_the_week}
                clearable
                variant="pill-md"
              />
            )}
          />
        </div>
      </div>
      <div className="flex items-center justify-end gap-2 border-t-[0.5px] border-subtle px-5 py-4">
        <Button variant="secondary" size="md" stretch="auto" onClick={handleClose} label={t("common.cancel")} />
        <Button
          variant="primary"
          size="md"
          stretch="auto"
          type="submit"
          loading={isSubmitting}
          label={
            data
              ? isSubmitting
                ? t("common.updating")
                : t("project_milestones.update_milestone")
              : isSubmitting
                ? t("common.creating")
                : t("common.create")
          }
        />
      </div>
    </form>
  );
});

export function MilestoneCreateUpdateModal(props: Props) {
  const { isOpen, handleClose, ...formProps } = props;

  return (
    <Dialog
      open={isOpen}
      disablePointerDismissal
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent size="md">
        <MilestoneForm handleClose={handleClose} {...formProps} />
      </DialogContent>
    </Dialog>
  );
}
