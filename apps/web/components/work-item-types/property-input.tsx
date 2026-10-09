/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment, useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { Switch } from "@makeplane/propel/components/switch";
import { TextArea, TextAreaGroup } from "@makeplane/propel/components/text-area";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { NewTabOutline } from "@makeplane/propel/icons";
// plane imports
import { Logo } from "@plane/blocks/emoji-icon-picker";
import { DateSelect } from "@plane/blocks/property-select";
import { Select } from "@plane/blocks/select";
import type { SelectVariant } from "@plane/blocks/select";
import { useTranslation } from "@plane/i18n";
import { EWorkItemPropertyRelationType, EWorkItemPropertyType } from "@plane/types";
import type { TWorkItemProperty, TWorkItemPropertyOption, TWorkItemPropertyValue } from "@plane/types";
import {
  getDate,
  getWorkItemPropertyPath,
  hasWorkItemPropertyEmptyMandatoryLevel,
  isWorkItemPropertyReadOnlyText,
  renderFormattedPayloadDate,
} from "@plane/utils";
// components
import { MemberSelect } from "@/components/dropdowns/member/member-select";
// hooks
import { useUserProfile } from "@/hooks/store/user";
// local imports
import { RichTextPropertyInput } from "./rich-text-property-input";

type TTextInputProps = {
  label: string;
  value: string;
  type: "text" | "number" | "url";
  isMultiLine?: boolean;
  placeholder: string;
  disabled: boolean;
  onSubmit: (value: string) => void;
};

/** Keeps what is typed to itself until the field is left or Enter is pressed, so that a value is saved once. */
function TextInput(props: TTextInputProps) {
  const { label, value, type, isMultiLine = false, placeholder, disabled, onSubmit } = props;
  // states
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const handleSubmit = () => {
    if (draft !== value) onSubmit(draft);
  };

  if (isMultiLine)
    return (
      <TextAreaGroup resize="none">
        <TextArea
          size="md"
          surface="field"
          autoResize
          maxRows={8}
          aria-label={label}
          placeholder={placeholder}
          value={draft}
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={handleSubmit}
        />
      </TextAreaGroup>
    );

  return (
    <InputGroup size="md">
      <Input
        size="md"
        type={type}
        step={type === "number" ? "any" : undefined}
        aria-label={label}
        placeholder={placeholder}
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={handleSubmit}
        onKeyDown={(event) => {
          if (event.key === "Enter") handleSubmit();
        }}
      />
      {type === "url" && value && (
        <a href={value} target="_blank" rel="noopener noreferrer" aria-label={value} className="px-2 text-tertiary">
          <NewTabOutline className="size-3.5" />
        </a>
      )}
    </InputGroup>
  );
}

type TOptionSelectProps = {
  // a dropdown, or what one level of a cascading property offers
  property: Pick<TWorkItemProperty, "options" | "is_multi" | "is_required">;
  value: TWorkItemPropertyValue | undefined;
  variant: SelectVariant;
  disabled: boolean;
  onChange: (value: TWorkItemPropertyValue) => void;
  placeholder?: string;
};

type TOption = Pick<TWorkItemPropertyOption, "id" | "name"> & Partial<Pick<TWorkItemPropertyOption, "logo_props">>;

const OptionSelect = observer(function OptionSelect(props: TOptionSelectProps) {
  const { property, value, variant, disabled, onChange, placeholder } = props;
  // plane hooks
  const { t } = useTranslation();
  // derived values
  const i18nPrefix = "work_item_types.settings.properties.attributes.option.select.placeholder";
  const commonProps = {
    getValues: () => property.options,
    getOptionValue: (option: TOption) => option.id,
    getOptionLabel: (option: TOption) => option.name,
    getOptionIcon: (option: TOption) =>
      option.logo_props?.in_use ? <Logo logo={option.logo_props} size={14} type="lucide" /> : undefined,
    disabled,
    pinSelected: false,
  };
  const trigger = (
    <Select.Trigger variant={variant} className="clickable">
      <Select.Value />
    </Select.Trigger>
  );

  if (property.is_multi)
    return (
      <Select<TOption>
        {...commonProps}
        multiple
        valueIds={Array.isArray(value) ? value : []}
        onChange={(optionIds) => onChange(optionIds.length ? optionIds : null)}
        placeholder={t(`${i18nPrefix}.multi.default`)}
      >
        {trigger}
      </Select>
    );

  return (
    <Select<TOption>
      {...commonProps}
      // an empty id is how a Select offers to clear a single selection
      headerItems={property.is_required ? undefined : [{ id: "", name: t("common.none") }]}
      value={property.options.find((option) => option.id === value) ?? null}
      onChange={(optionId) => onChange(optionId || null)}
      placeholder={placeholder ?? t(`${i18nPrefix}.single`)}
    >
      {trigger}
    </Select>
  );
});

type TCascadingSelectProps = Omit<TOptionSelectProps, "property" | "placeholder"> & { property: TWorkItemProperty };

/**
 * The linked dropdowns of a cascading property, one for every level: a dropdown offers the options under
 * the option chosen in the one before it, and choosing in it clears those after it.
 */
const CascadingSelect = observer(function CascadingSelect(props: TCascadingSelectProps) {
  const { property, value, variant, disabled, onChange } = props;
  // states
  // the options chosen so far, while a mandatory level still has none: the server saves no such selection
  const [pendingIds, setPendingIds] = useState<string[] | null>(null);
  // plane hooks
  const { t } = useTranslation();
  // derived values
  const selectedIds = pendingIds ?? (Array.isArray(value) ? value : []);

  const handleChange = (levelIndex: number, optionId: TWorkItemPropertyValue) => {
    const optionIds = selectedIds.slice(0, levelIndex);
    if (typeof optionId === "string") optionIds.push(optionId);
    if (hasWorkItemPropertyEmptyMandatoryLevel(property, optionIds)) setPendingIds(optionIds);
    else {
      setPendingIds(null);
      onChange(optionIds.length ? optionIds : null);
    }
  };

  return (
    <div className="flex w-full flex-col gap-1">
      {(property.settings.levels ?? []).slice(0, selectedIds.length + 1).map((level, levelIndex) => {
        const parentId = levelIndex === 0 ? null : selectedIds[levelIndex - 1];
        const options = property.options.filter((option) => option.parent === parentId);
        const label = property.options.find((option) => option.id === parentId)?.sub_level_label || level.name;
        if (levelIndex > 0 && options.length === 0) return null;
        return (
          // oxlint-disable-next-line react/no-array-index-key -- levels keep their order
          <Fragment key={levelIndex}>
            <OptionSelect
              property={{ options, is_multi: false, is_required: level.is_required }}
              value={selectedIds[levelIndex]}
              variant={variant}
              disabled={disabled}
              onChange={(optionId) => handleChange(levelIndex, optionId)}
              placeholder={label}
            />
            {level.is_required && selectedIds.length === levelIndex && levelIndex > 0 && (
              <span className="px-2 text-caption-sm-regular text-danger-primary">
                {t("common.errors.entity_required", { entity: label })}
              </span>
            )}
          </Fragment>
        );
      })}
    </div>
  );
});

export type TWorkItemPropertyInputProps = {
  property: TWorkItemProperty;
  // the stored value, or the computed one of a formula
  value: TWorkItemPropertyValue | undefined;
  onChange: (value: TWorkItemPropertyValue) => void;
  variant: SelectVariant;
  projectId: string;
  disabled?: boolean;
  formulaError?: string;
  // the rich text editor attaches its uploads to the work item
  workItemId?: string;
  isDraft?: boolean;
  onAssetUpload?: (assetId: string) => void;
};

/**
 * The control of a property, by its type. Every value of a work item is edited through it: in the detail
 * sidebar, in the peek view, in the create and update modal and in a table cell.
 */
export const WorkItemPropertyInput = observer(function WorkItemPropertyInput(props: TWorkItemPropertyInputProps) {
  const { property, value, onChange, variant, projectId, disabled = false, formulaError } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { data: userProfile } = useUserProfile();
  // derived values
  const i18nPrefix = "work_item_types.settings.properties.attributes";
  const textValue = typeof value === "string" ? value : "";

  switch (property.property_type) {
    case EWorkItemPropertyType.FORMULA:
      return (
        <Tooltip label={formulaError} disabled={!formulaError}>
          <span className={`truncate px-2 text-body-xs-regular ${formulaError ? "text-danger-primary" : ""}`}>
            {formulaError ? t("common.errors.default.title") : String(value ?? "")}
          </span>
        </Tooltip>
      );
    case EWorkItemPropertyType.TEXT:
      if (isWorkItemPropertyReadOnlyText(property))
        return <span className="px-2 text-body-xs-regular whitespace-pre-wrap">{property.default_value[0]}</span>;
      return (
        <TextInput
          label={property.display_name}
          value={textValue}
          type="text"
          // a table row has the height of one line
          isMultiLine={property.settings.display_format === "multi-line" && variant !== "table-cell"}
          placeholder={t(`${i18nPrefix}.text.placeholder`)}
          disabled={disabled}
          onSubmit={(text) => onChange(text || null)}
        />
      );
    case EWorkItemPropertyType.URL:
    case EWorkItemPropertyType.DECIMAL: {
      const isNumber = property.property_type === EWorkItemPropertyType.DECIMAL;
      return (
        <TextInput
          label={property.display_name}
          value={isNumber && typeof value === "number" ? String(value) : textValue}
          type={isNumber ? "number" : "url"}
          placeholder={t(isNumber ? `${i18nPrefix}.number.default.placeholder` : `${i18nPrefix}.url.placeholder`)}
          disabled={disabled}
          onSubmit={(text) => onChange(text === "" ? null : isNumber ? Number(text) : text)}
        />
      );
    }
    case EWorkItemPropertyType.BOOLEAN:
      return (
        <span className="flex h-7.5 items-center px-2">
          <Switch
            size="sm"
            aria-label={property.display_name}
            checked={value === true}
            disabled={disabled}
            onCheckedChange={(checked) => onChange(checked)}
          />
        </span>
      );
    case EWorkItemPropertyType.DATETIME:
      return (
        <DateSelect
          value={getDate(textValue) ?? null}
          onChange={(date) => onChange((date && renderFormattedPayloadDate(date)) ?? null)}
          formatToken={property.settings.display_format}
          placeholder={t(`${i18nPrefix}.date.placeholder`)}
          weekStartsOn={userProfile?.start_of_the_week}
          disabled={disabled}
          clearable={!property.is_required}
          variant={variant}
          className="clickable"
        />
      );
    case EWorkItemPropertyType.OPTION:
      return (
        <OptionSelect property={property} value={value} variant={variant} disabled={disabled} onChange={onChange} />
      );
    case EWorkItemPropertyType.CASCADING:
      // a table row has the height of one line: it shows the chosen path, which is changed in the work item
      if (variant === "table-cell")
        return <span className="truncate px-2 text-body-xs-regular">{getWorkItemPropertyPath(property, value)}</span>;
      return (
        <CascadingSelect
          // a selection that is still being made stays with the work item it was started on
          key={props.workItemId}
          property={property}
          value={value}
          variant={variant}
          disabled={disabled}
          onChange={onChange}
        />
      );
    case EWorkItemPropertyType.RELATION:
      if (property.relation_type === EWorkItemPropertyRelationType.RICH_TEXT)
        return (
          <RichTextPropertyInput
            id={`${props.workItemId ?? "work-item-modal"}-${property.id}`}
            value={typeof value === "string" ? value : undefined}
            onChange={onChange}
            projectId={projectId}
            placeholder={t(`${i18nPrefix}.text.placeholder`)}
            disabled={disabled}
            workItemId={props.workItemId}
            isDraft={props.isDraft}
            onAssetUpload={props.onAssetUpload}
          />
        );
      if (property.is_multi)
        return (
          <MemberSelect
            multiple
            value={Array.isArray(value) ? value : []}
            onChange={(memberIds) => onChange(memberIds.length ? memberIds : null)}
            projectId={projectId}
            placeholder={t("add_members")}
            disabled={disabled}
            variant={variant}
            className="clickable"
          />
        );
      return (
        <MemberSelect
          value={textValue || null}
          onChange={(memberId) => onChange(memberId || null)}
          projectId={projectId}
          placeholder={t("add_members")}
          clearable={!property.is_required}
          disabled={disabled}
          variant={variant}
          className="clickable"
        />
      );
  }
});
