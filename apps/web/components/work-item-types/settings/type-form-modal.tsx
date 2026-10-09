/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Button } from "@makeplane/propel/components/button";
import { Dialog, DialogContent } from "@makeplane/propel/components/dialog";
import { Field } from "@makeplane/propel/components/field";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { TextArea, TextAreaGroup } from "@makeplane/propel/components/text-area";
// plane imports
import { EmojiPicker } from "@plane/blocks/emoji-icon-picker";
import { getRandomIconName } from "@plane/blocks/emoji-icon-picker/data";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TWorkItemType } from "@plane/types";
import { generateIconColors } from "@plane/utils";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WorkItemTypeLogo } from "../type-logo";

type TFormValues = Pick<TWorkItemType, "name" | "description" | "logo_props">;

type Props = {
  onClose: () => void;
  workspaceSlug: string;
  projectId: string;
  // the type to update; a new type is created without it
  type?: TWorkItemType;
};

const DEFAULT_ICON_COLOR = "#6d7b8a";

// The picker gives an icon and its colour; the background is a tint of that colour.
const getLogoProps = (name: string, color: string): TWorkItemType["logo_props"] => ({
  in_use: "icon",
  icon: { name, color, background_color: generateIconColors(color).background },
});

export function WorkItemTypeFormModal(props: Props) {
  const { onClose, workspaceSlug, projectId, type } = props;
  // states
  const [isIconPickerOpen, setIsIconPickerOpen] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { createWorkItemType, updateWorkItemType } = useWorkItemTypes();
  // form info
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    control,
    watch,
    setValue,
  } = useForm<TFormValues>({
    defaultValues: {
      name: type?.name ?? "",
      description: type?.description ?? "",
      // a new type gets a glyph to start with; the types the server created have none until one is picked
      logo_props: type ? type.logo_props : getLogoProps(getRandomIconName(), DEFAULT_ICON_COLOR),
    },
  });
  // derived values
  const i18nPrefix = type ? "work_item_types.update" : "work_item_types.create";
  const logoProps = watch("logo_props");

  const handleFormSubmit = async (formData: TFormValues) => {
    try {
      if (type) await updateWorkItemType(workspaceSlug, projectId, type.id, formData);
      else await createWorkItemType(workspaceSlug, projectId, formData);
      setToast({
        type: "success",
        title: t(`${i18nPrefix}.toast.success.title`),
        message: t(`${i18nPrefix}.toast.success.message`, { name: formData.name }),
      });
      onClose();
    } catch (error) {
      const isNameTaken = !!error && typeof error === "object" && "name" in error;
      setToast({
        type: "error",
        title: t(`${i18nPrefix}.toast.error.title`),
        message: t(`${i18nPrefix}.toast.error.message.${isNameTaken ? "conflict" : "default"}`, {
          name: formData.name,
        }),
      });
    }
  };

  return (
    <Dialog
      open
      disablePointerDismissal
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent size="md">
        <form onSubmit={handleSubmit(handleFormSubmit)}>
          <div className="space-y-5 p-5">
            <h3 className="text-18 font-medium text-secondary">{t(`${i18nPrefix}.title`)}</h3>
            <div className="flex items-start gap-3">
              <EmojiPicker
                isOpen={isIconPickerOpen}
                handleToggle={setIsIconPickerOpen}
                showEmojiTab={false}
                defaultOpen="icon"
                defaultIconColor={logoProps.icon?.color ?? DEFAULT_ICON_COLOR}
                label={<WorkItemTypeLogo logoProps={logoProps} size={40} />}
                onChange={(logo) => {
                  if (logo.type === "icon") setValue("logo_props", getLogoProps(logo.value.name, logo.value.color));
                }}
              />
              <div className="flex-1 space-y-3">
                <div className="space-y-1">
                  <Controller
                    control={control}
                    name="name"
                    rules={{
                      required: t("name_is_required"),
                      maxLength: { value: 255, message: t("title_should_be_less_than_255_characters") },
                    }}
                    render={({ field: { value, onChange } }) => (
                      <Field name="name" invalid={Boolean(errors?.name)}>
                        <InputGroup size="xl">
                          <Input
                            size="xl"
                            name="name"
                            type="text"
                            placeholder={t("work_item_types.create_update.form.name.placeholder")}
                            aria-label={t("common.name")}
                            value={value}
                            onChange={onChange}
                          />
                        </InputGroup>
                      </Field>
                    )}
                  />
                  <span className="text-11 text-danger-primary">{errors?.name?.message}</span>
                </div>
                <TextAreaGroup resize="none">
                  <TextArea
                    size="lg"
                    surface="field"
                    autoResize
                    maxRows={6}
                    placeholder={t("work_item_types.create_update.form.description.placeholder")}
                    value={watch("description")}
                    onChange={(event) => setValue("description", event.target.value)}
                  />
                </TextAreaGroup>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 border-t-[0.5px] border-subtle px-5 py-4">
            <Button variant="secondary" size="md" stretch="auto" onClick={onClose} label={t("common.cancel")} />
            <Button
              variant="primary"
              size="md"
              stretch="auto"
              type="submit"
              loading={isSubmitting}
              label={t(type ? "work_item_types.update.button" : "work_item_types.create.title")}
            />
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
