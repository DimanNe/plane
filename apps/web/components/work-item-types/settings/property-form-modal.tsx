/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { isEqual } from "lodash-es";
import { observer } from "mobx-react";
import { Controller, FormProvider, useForm } from "react-hook-form";
import { Button } from "@makeplane/propel/components/button";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { Dialog, DialogContent } from "@makeplane/propel/components/dialog";
import { Field } from "@makeplane/propel/components/field";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { TextArea, TextAreaGroup } from "@makeplane/propel/components/text-area";
// plane imports
import { setToast } from "@plane/blocks/toast";
import {
  WORK_ITEM_PROPERTY_DATE_FORMATS,
  WORK_ITEM_PROPERTY_MIN_LEVELS,
  WORK_ITEM_PROPERTY_TEXT_FORMATS,
  WORK_ITEM_PROPERTY_TYPES,
} from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TWorkItemProperty, TWorkItemPropertyPayload, TWorkItemPropertyTypeKey } from "@plane/types";
import { getWorkItemPropertyTypeKey } from "@plane/utils";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
import { useUntouchedDialog } from "@/hooks/use-untouched-dialog";
// local imports
import { WORK_ITEM_PROPERTY_TYPE_ICONS } from "../property-icon";
import { ChoiceSelect } from "./choice-select";
import { WorkItemPropertyAttributes } from "./property-attributes";
import type { TWorkItemPropertyFormValues } from "./property-attributes";
import { WorkItemPropertySavedOptions } from "./property-saved-options";

type Props = {
  onClose: () => void;
  workspaceSlug: string;
  projectId: string;
  typeId: string;
  // the property to update; a new property is created without it
  property?: TWorkItemProperty;
};

const DEFAULT_SETTINGS: Partial<Record<TWorkItemPropertyTypeKey, TWorkItemProperty["settings"]>> = {
  TEXT: { display_format: WORK_ITEM_PROPERTY_TEXT_FORMATS[0].key },
  DATETIME: { display_format: WORK_ITEM_PROPERTY_DATE_FORMATS[0] },
  FORMULA: { expression: "" },
};

export const WorkItemPropertyFormModal = observer(function WorkItemPropertyFormModal(props: Props) {
  const { onClose, workspaceSlug, projectId, typeId, property } = props;
  // states
  const [createdPropertyId, setCreatedPropertyId] = useState<string>();
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { propertyMap, createWorkItemProperty, updateWorkItemProperty } = useWorkItemTypes();
  // form info
  const methods = useForm<TWorkItemPropertyFormValues>({
    defaultValues: {
      display_name: property?.display_name ?? "",
      description: property?.description ?? "",
      type_key: property ? getWorkItemPropertyTypeKey(property) : null,
      is_multi: property?.is_multi ?? false,
      is_required: property?.is_required ?? false,
      is_active: property?.is_active ?? true,
      settings: property?.settings ?? {},
      default_value: property?.default_value ?? [],
      options: [],
    },
  });
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    control,
    watch,
    setValue,
    setError,
  } = methods;
  // derived values
  const i18nPrefix = "work_item_types.settings.properties";
  const action = property ? "update" : "create";
  const typeKey = watch("type_key");
  // a boolean always has a value, a formula and a read-only text never take one, and a cascading property
  // is mandatory level by level
  const canBeMandatory =
    typeKey !== "BOOLEAN" &&
    typeKey !== "FORMULA" &&
    typeKey !== "CASCADING" &&
    !(typeKey === "TEXT" && watch("settings").display_format === "readonly");
  // the docs: a cascading property starts with two levels named Level 1 and Level 2
  const defaultLevels = Array.from({ length: WORK_ITEM_PROPERTY_MIN_LEVELS }, (_, index) => ({
    name: t(`${i18nPrefix}.attributes.cascading.level_name`, { number: index + 1 }),
    is_required: false,
  }));
  const createdProperty = createdPropertyId ? propertyMap[createdPropertyId] : undefined;

  // What the chosen type needs before it can be saved. The fields of one type give way to those of another
  // as the type changes, so this is checked here and not by rules that would stay behind on a field.
  const getAttributesError = (formData: TWorkItemPropertyFormValues) => {
    if (formData.type_key === "OPTION" && !property && formData.options.length === 0)
      return t(`${i18nPrefix}.create_update.errors.options.required`);
    if (formData.type_key === "FORMULA" && !formData.settings.expression?.trim())
      return t(`${i18nPrefix}.create_update.errors.formula.required`);
    if (formData.type_key === "CASCADING" && formData.settings.levels?.some((level) => !level.name.trim()))
      return t(`${i18nPrefix}.create_update.errors.levels.required`);
    if (
      formData.type_key === "TEXT" &&
      formData.settings.display_format === "readonly" &&
      !formData.default_value[0]?.trim()
    )
      return t("common.errors.required");
    return undefined;
  };

  const handleFormSubmit = async (formData: TWorkItemPropertyFormValues) => {
    if (!formData.type_key) return;
    const attributesError = getAttributesError(formData);
    if (attributesError) {
      setError("root", { message: attributesError });
      return;
    }
    const payload: TWorkItemPropertyPayload = {
      display_name: formData.display_name,
      description: formData.description,
      is_required: canBeMandatory && formData.is_required,
      is_active: formData.is_active,
      default_value: formData.default_value,
    };
    // The server validates settings whenever a request carries them. A formula whose source has been renamed
    // would be refused, so an update that leaves the settings alone leaves them out.
    if (!property || !isEqual(formData.settings, property.settings)) payload.settings = formData.settings;
    try {
      const savedProperty = property
        ? await updateWorkItemProperty(workspaceSlug, projectId, property.id, payload)
        : await createWorkItemProperty(workspaceSlug, projectId, typeId, {
            ...payload,
            property_type: WORK_ITEM_PROPERTY_TYPES[formData.type_key].property_type,
            relation_type: WORK_ITEM_PROPERTY_TYPES[formData.type_key].relation_type,
            is_multi: formData.is_multi,
            options: formData.options,
          });
      setToast({
        type: "success",
        title: t(`${i18nPrefix}.toast.${action}.success.title`),
        message: t(`${i18nPrefix}.toast.${action}.success.message`, { name: formData.display_name }),
      });
      // the options of a cascading property are saved under the saved property, so creating one leads on to them
      if (!property && formData.type_key === "CASCADING") setCreatedPropertyId(savedProperty.id);
      else onClose();
    } catch (error) {
      // the server names the field it refuses: a name the type already has, a formula it cannot evaluate
      const fieldErrors = (error ?? {}) as { display_name?: string[]; settings?: { expression?: string[] } };
      if (fieldErrors.display_name) setError("display_name", { message: fieldErrors.display_name[0] });
      if (fieldErrors.settings?.expression)
        setError("root", {
          message: t(`${i18nPrefix}.create_update.errors.formula.invalid`, {
            error: fieldErrors.settings.expression[0],
          }),
        });
      setToast({
        type: "error",
        title: t(`${i18nPrefix}.toast.${action}.error.title`),
        message: t(`${i18nPrefix}.toast.${action}.error.message`),
      });
    }
  };

  const { popupRef, shouldIgnoreOutsidePress } = useUntouchedDialog();

  if (createdProperty)
    return (
      <Dialog
        open
        onOpenChange={(open, eventDetails) => {
          if (!open && !shouldIgnoreOutsidePress(eventDetails)) onClose();
        }}
      >
        <DialogContent size="lg" ref={popupRef}>
          <div className="space-y-5 p-5">
            <h3 className="text-18 font-medium text-secondary">
              {t(`${i18nPrefix}.attributes.cascading.add_options`)}
            </h3>
            <div className="max-h-[50vh] overflow-y-auto">
              <WorkItemPropertySavedOptions
                workspaceSlug={workspaceSlug}
                projectId={projectId}
                property={createdProperty}
              />
            </div>
          </div>
          <div className="flex justify-end border-t-[0.5px] border-subtle px-5 py-4">
            <Button
              variant="secondary"
              size="md"
              stretch="auto"
              onClick={onClose}
              label={t(createdProperty.options.length ? "common.done" : `${i18nPrefix}.attributes.cascading.skip`)}
            />
          </div>
        </DialogContent>
      </Dialog>
    );

  return (
    <Dialog
      open
      onOpenChange={(open, eventDetails) => {
        if (!open && !shouldIgnoreOutsidePress(eventDetails)) onClose();
      }}
    >
      <DialogContent size="lg" ref={popupRef}>
        <FormProvider {...methods}>
          <form onSubmit={handleSubmit(handleFormSubmit)}>
            <div className="space-y-5 p-5">
              <h3 className="text-18 font-medium text-secondary">{t(`${i18nPrefix}.create_update.title.${action}`)}</h3>
              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-3">
                  <div className="space-y-1">
                    <Controller
                      control={control}
                      name="display_name"
                      rules={{
                        required: t(`${i18nPrefix}.create_update.errors.name.required`),
                        maxLength: { value: 255, message: t(`${i18nPrefix}.create_update.errors.name.max_length`) },
                      }}
                      render={({ field: { value, onChange } }) => (
                        <Field name="display_name" invalid={Boolean(errors.display_name)}>
                          <InputGroup size="xl">
                            <Input
                              size="xl"
                              name="display_name"
                              type="text"
                              placeholder={t(`${i18nPrefix}.create_update.form.display_name.placeholder`)}
                              aria-label={t(`${i18nPrefix}.create_update.form.display_name.placeholder`)}
                              value={value}
                              onChange={onChange}
                            />
                          </InputGroup>
                        </Field>
                      )}
                    />
                    <span className="text-11 text-danger-primary">{errors.display_name?.message}</span>
                  </div>
                  <TextAreaGroup resize="none">
                    <TextArea
                      size="lg"
                      surface="field"
                      autoResize
                      maxRows={6}
                      placeholder={t(`${i18nPrefix}.create_update.form.description.placeholder`)}
                      value={watch("description")}
                      onChange={(event) => setValue("description", event.target.value)}
                    />
                  </TextAreaGroup>
                </div>
                <div className="space-y-3">
                  <div className="space-y-1">
                    <span className="text-caption-md-medium text-tertiary">{t(`${i18nPrefix}.dropdown.label`)}</span>
                    <Controller
                      control={control}
                      name="type_key"
                      rules={{ required: t(`${i18nPrefix}.create_update.errors.property_type.required`) }}
                      render={({ field: { value, onChange } }) => (
                        <ChoiceSelect
                          choices={Object.entries(WORK_ITEM_PROPERTY_TYPES).map(([key, details]) => {
                            const Icon = WORK_ITEM_PROPERTY_TYPE_ICONS[key as TWorkItemPropertyTypeKey];
                            return { key, label: t(details.i18n_label), icon: <Icon className="size-3.5" /> };
                          })}
                          value={value}
                          onChange={(key) => {
                            onChange(key);
                            setValue(
                              "settings",
                              key === "CASCADING"
                                ? { levels: defaultLevels }
                                : (DEFAULT_SETTINGS[key as TWorkItemPropertyTypeKey] ?? {})
                            );
                            setValue("default_value", []);
                            setValue("is_multi", false);
                          }}
                          placeholder={t(`${i18nPrefix}.dropdown.placeholder`)}
                          // the type decides the shape of the stored values, so it is fixed at creation
                          disabled={!!property}
                        />
                      )}
                    />
                    <span className="text-11 text-danger-primary">{errors.type_key?.message}</span>
                  </div>
                  <WorkItemPropertyAttributes workspaceSlug={workspaceSlug} projectId={projectId} property={property} />
                </div>
              </div>
              {property && typeKey === "CASCADING" && (
                <div className="space-y-2">
                  <span className="text-body-sm-medium text-secondary">
                    {t(`${i18nPrefix}.attributes.cascading.manage_options`)}
                  </span>
                  <div className="max-h-[40vh] overflow-y-auto">
                    <WorkItemPropertySavedOptions
                      workspaceSlug={workspaceSlug}
                      projectId={projectId}
                      property={property}
                    />
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between gap-2 border-t-[0.5px] border-subtle px-5 py-4">
              <div className="flex items-center gap-4">
                <Checkbox
                  label={t(`${i18nPrefix}.mandate_confirmation.label`)}
                  checked={canBeMandatory && watch("is_required")}
                  disabled={!canBeMandatory}
                  onCheckedChange={(checked) => setValue("is_required", checked)}
                />
                <Checkbox
                  label={t(`${i18nPrefix}.enable_disable.label`)}
                  checked={watch("is_active")}
                  onCheckedChange={(checked) => setValue("is_active", checked)}
                />
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="md" stretch="auto" onClick={onClose} label={t("common.cancel")} />
                <Button
                  variant="primary"
                  size="md"
                  stretch="auto"
                  type="submit"
                  loading={isSubmitting}
                  label={t(property ? "common.update" : "common.create")}
                />
              </div>
            </div>
          </form>
        </FormProvider>
      </DialogContent>
    </Dialog>
  );
});
