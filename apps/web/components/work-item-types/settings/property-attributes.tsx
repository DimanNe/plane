/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useFormContext } from "react-hook-form";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { TextArea, TextAreaGroup } from "@makeplane/propel/components/text-area";
// plane imports
import { WORK_ITEM_PROPERTY_DATE_FORMATS, WORK_ITEM_PROPERTY_TEXT_FORMATS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type {
  TWorkItemProperty,
  TWorkItemPropertyOptionPayload,
  TWorkItemPropertyPayload,
  TWorkItemPropertyTypeKey,
} from "@plane/types";
import { renderFormattedDate } from "@plane/utils";
// local imports
import { ChoiceSelect } from "./choice-select";
import { WorkItemPropertyLevelsEditor } from "./property-levels-editor";
import { WorkItemPropertyOptionsEditor } from "./property-options-editor";
import { WorkItemPropertySavedOptions } from "./property-saved-options";

export type TWorkItemPropertyFormValues = Required<
  Pick<
    TWorkItemPropertyPayload,
    "display_name" | "description" | "is_multi" | "is_required" | "is_active" | "settings" | "default_value" | "options"
  >
> & { type_key: TWorkItemPropertyTypeKey | null };

type Props = {
  workspaceSlug: string;
  projectId: string;
  // the property being updated; its options are saved one by one, those of a new dropdown with the form
  property?: TWorkItemProperty;
};

/** The fields of the property form that depend on the property type. */
export const WorkItemPropertyAttributes = observer(function WorkItemPropertyAttributes(props: Props) {
  const { workspaceSlug, projectId, property } = props;
  // plane hooks
  const { t } = useTranslation();
  // form info
  const {
    watch,
    setValue,
    formState: { errors },
  } = useFormContext<TWorkItemPropertyFormValues>();
  // derived values
  const i18nPrefix = "work_item_types.settings.properties";
  const typeKey = watch("type_key");
  const settings = watch("settings");
  const isMulti = watch("is_multi");
  const defaultValue = watch("default_value")[0] ?? "";
  const options = watch("options");
  const today = new Date();

  const handleOptionUpdate = (index: number, data: TWorkItemPropertyOptionPayload) =>
    setValue(
      "options",
      options.map((option, optionIndex) => {
        if (optionIndex === index) return { ...option, ...data };
        return data.is_default && !isMulti ? { ...option, is_default: false } : option;
      })
    );

  return (
    <>
      {typeKey === "TEXT" && (
        <ChoiceSelect
          choices={WORK_ITEM_PROPERTY_TEXT_FORMATS.map(({ key, i18n_label }) => ({ key, label: t(i18n_label) }))}
          value={settings.display_format ?? null}
          onChange={(key) => {
            setValue("settings", { display_format: key });
            setValue("default_value", []);
          }}
          // stored values of a text property follow its format, so the format is fixed at creation
          disabled={!!property}
        />
      )}
      {typeKey === "TEXT" && settings.display_format === "readonly" && (
        <TextAreaGroup resize="none">
          <TextArea
            size="md"
            surface="field"
            autoResize
            maxRows={6}
            placeholder={t(`${i18nPrefix}.attributes.text.readonly.header`)}
            aria-label={t(`${i18nPrefix}.attributes.text.readonly.header`)}
            value={defaultValue}
            onChange={(event) => setValue("default_value", event.target.value ? [event.target.value] : [])}
          />
        </TextAreaGroup>
      )}
      {typeKey === "DECIMAL" && (
        <InputGroup size="md">
          <Input
            size="md"
            type="number"
            step="any"
            placeholder={t(`${i18nPrefix}.attributes.number.default.placeholder`)}
            aria-label={t(`${i18nPrefix}.attributes.number.default.placeholder`)}
            value={defaultValue}
            onChange={(event) => setValue("default_value", event.target.value ? [event.target.value] : [])}
          />
        </InputGroup>
      )}
      {typeKey === "DATETIME" && (
        <div className="space-y-1">
          <span className="text-caption-md-medium text-tertiary">
            {t(`${i18nPrefix}.attributes.date.display_format`)}
          </span>
          <ChoiceSelect
            choices={WORK_ITEM_PROPERTY_DATE_FORMATS.map((format) => ({
              key: format,
              label: renderFormattedDate(today, format) ?? format,
            }))}
            value={settings.display_format ?? null}
            onChange={(key) => setValue("settings", { display_format: key })}
          />
        </div>
      )}
      {(typeKey === "OPTION" || typeKey === "RELATION_USER") && (
        <ChoiceSelect
          choices={[
            { key: "single", label: t(`${i18nPrefix}.attributes.relation.single_select.label`) },
            { key: "multi", label: t(`${i18nPrefix}.attributes.relation.multi_select.label`) },
          ]}
          value={isMulti ? "multi" : "single"}
          onChange={(key) => setValue("is_multi", key === "multi")}
          // one selection is stored as an id and several as a list, so this is fixed at creation
          disabled={!!property}
        />
      )}
      {typeKey === "OPTION" &&
        (property ? (
          <WorkItemPropertySavedOptions workspaceSlug={workspaceSlug} projectId={projectId} property={property} />
        ) : (
          <WorkItemPropertyOptionsEditor
            options={options}
            onAdd={(name) => setValue("options", [...options, { name }])}
            onUpdate={handleOptionUpdate}
            onRemove={(index) =>
              setValue(
                "options",
                options.filter((_option, optionIndex) => optionIndex !== index)
              )
            }
          />
        ))}
      {typeKey === "CASCADING" && (
        <WorkItemPropertyLevelsEditor
          levels={settings.levels ?? []}
          onChange={(levels) => setValue("settings", { levels })}
          savedLevelCount={property?.settings.levels?.length ?? 0}
        />
      )}
      {typeKey === "FORMULA" && (
        <div className="space-y-1">
          <TextAreaGroup resize="none">
            <TextArea
              size="md"
              surface="field"
              autoResize
              maxRows={6}
              placeholder={t(`${i18nPrefix}.formula.placeholder`)}
              aria-label={t(`${i18nPrefix}.formula.field_label`)}
              value={settings.expression ?? ""}
              onChange={(event) => setValue("settings", { expression: event.target.value })}
            />
          </TextAreaGroup>
          <p className="text-caption-sm-regular text-tertiary">{t(`${i18nPrefix}.formula.help`)}</p>
        </div>
      )}
      <span className="text-11 text-danger-primary">{errors.root?.message}</span>
    </>
  );
});
