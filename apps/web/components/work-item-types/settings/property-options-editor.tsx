/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { AddOutline, ChevronDownOutline, CloseOutline } from "@makeplane/propel/icons";
// plane imports
import { EmojiPicker, Logo } from "@plane/blocks/emoji-icon-picker";
import { useTranslation } from "@plane/i18n";
import type { TWorkItemPropertyOptionPayload } from "@plane/types";
import { cn } from "@plane/utils";

type TOptionTextInputProps = {
  label: string;
  value: string;
  placeholder?: string;
  isRequired?: boolean;
  onSubmit: (value: string) => void;
};

/** Keeps what is typed to itself until the field is left or Enter is pressed, so that it is saved once. */
function OptionTextInput(props: TOptionTextInputProps) {
  const { label, value, placeholder, isRequired = false, onSubmit } = props;
  // states
  const [text, setText] = useState(value);

  return (
    <InputGroup size="md">
      <Input
        size="md"
        aria-label={label}
        placeholder={placeholder}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onBlur={() => {
          const trimmedText = text.trim();
          if (trimmedText !== value && (trimmedText || !isRequired)) onSubmit(trimmedText);
          else setText(value);
        }}
        onKeyDown={(event) => {
          if (event.key !== "Enter") return;
          // Enter saves as leaving the field does; it must not submit the property form
          event.preventDefault();
          event.currentTarget.blur();
        }}
      />
    </InputGroup>
  );
}

type TOptionRowProps = {
  option: TWorkItemPropertyOptionPayload;
  onUpdate: (data: TWorkItemPropertyOptionPayload) => void;
  onRemove: () => void;
  isCascading: boolean;
  nextLevelName?: string;
  // the options under this one
  children?: React.ReactNode;
};

const OptionRow = observer(function OptionRow(props: TOptionRowProps) {
  const { option, onUpdate, onRemove, isCascading, nextLevelName, children } = props;
  // states
  const [isIconPickerOpen, setIsIconPickerOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  // plane hooks
  const { t } = useTranslation();

  return (
    <>
      <div className="flex items-center gap-2">
        {nextLevelName && (
          <IconButton
            variant="ghost"
            size="sm"
            icon={
              <Icon
                icon={<ChevronDownOutline className={cn("transition-transform", { "-rotate-90": !isExpanded })} />}
              />
            }
            aria-label={option.sub_level_label || nextLevelName}
            aria-expanded={isExpanded}
            onClick={() => setIsExpanded(!isExpanded)}
          />
        )}
        {!isCascading && (
          <EmojiPicker
            isOpen={isIconPickerOpen}
            handleToggle={setIsIconPickerOpen}
            label={
              <span className="grid size-7 place-items-center rounded-sm border-[0.5px] border-subtle">
                {option.logo_props?.in_use ? (
                  <Logo logo={option.logo_props} size={14} type="lucide" />
                ) : (
                  <AddOutline className="size-3.5 text-placeholder" />
                )}
              </span>
            }
            onChange={(logo) =>
              onUpdate({
                logo_props:
                  logo.type === "emoji"
                    ? { in_use: "emoji", emoji: { value: logo.value } }
                    : { in_use: "icon", icon: logo.value },
              })
            }
          />
        )}
        <div className="grow">
          <OptionTextInput
            label={t("common.name")}
            value={option.name ?? ""}
            isRequired
            onSubmit={(name) => onUpdate({ name })}
          />
        </div>
        {nextLevelName && (
          <div className="w-1/3">
            <OptionTextInput
              label={t("work_item_types.settings.properties.attributes.cascading.sub_level_label")}
              value={option.sub_level_label ?? ""}
              placeholder={nextLevelName}
              onSubmit={(subLevelLabel) => onUpdate({ sub_level_label: subLevelLabel })}
            />
          </div>
        )}
        {!isCascading && (
          <Checkbox
            label={t("common.default")}
            checked={!!option.is_default}
            onCheckedChange={(checked) => onUpdate({ is_default: checked })}
          />
        )}
        <IconButton
          variant="ghost"
          size="sm"
          icon={<Icon icon={CloseOutline} />}
          aria-label={t("common.remove")}
          onClick={onRemove}
        />
      </div>
      {nextLevelName && isExpanded && <div className="ml-3.5 border-l border-subtle pl-3">{children}</div>}
    </>
  );
});

type Props = {
  // the name of the level the options are on, for a cascading property
  label?: string;
  options: (TWorkItemPropertyOptionPayload & { id?: string })[];
  onAdd: (name: string) => void;
  onUpdate: (index: number, data: TWorkItemPropertyOptionPayload) => void;
  onRemove: (index: number) => void;
  // an option of a cascading property has a name only
  isCascading?: boolean;
  // above the last level of a cascading property, an option opens onto the options under it and can
  // give them a label of its own in place of the name of their level
  nextLevelName?: string;
  renderOptionsUnder?: (index: number) => React.ReactNode;
};

export const WorkItemPropertyOptionsEditor = observer(function WorkItemPropertyOptionsEditor(props: Props) {
  const { label, options, onAdd, onUpdate, onRemove, isCascading = false, nextLevelName, renderOptionsUnder } = props;
  // states
  const [newOptionName, setNewOptionName] = useState("");
  // plane hooks
  const { t } = useTranslation();
  // derived values
  const i18nPrefix = "work_item_types.settings.properties.attributes.option.create_update";
  const trimmedName = newOptionName.trim();
  const isNameTaken = options.some((option) => option.name?.toLowerCase() === trimmedName.toLowerCase());

  const handleAdd = () => {
    if (!trimmedName || isNameTaken) return;
    onAdd(trimmedName);
    setNewOptionName("");
  };

  return (
    <div className="flex flex-col gap-2">
      <span className="text-caption-md-medium text-tertiary">{label ?? t(`${i18nPrefix}.label`)}</span>
      {options.map((option, index) => (
        <OptionRow
          key={option.id ?? option.name}
          option={option}
          onUpdate={(data) => onUpdate(index, data)}
          onRemove={() => onRemove(index)}
          isCascading={isCascading}
          nextLevelName={nextLevelName}
        >
          {renderOptionsUnder?.(index)}
        </OptionRow>
      ))}
      <div className="flex items-center gap-2">
        <div className="grow">
          <InputGroup size="md">
            <Input
              size="md"
              placeholder={t(`${i18nPrefix}.form.placeholder`)}
              aria-label={t(`${i18nPrefix}.form.placeholder`)}
              value={newOptionName}
              onChange={(event) => setNewOptionName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return;
                // Enter adds the option; it must not submit the property form around this field
                event.preventDefault();
                handleAdd();
              }}
            />
          </InputGroup>
        </div>
        <IconButton
          variant="secondary"
          size="sm"
          icon={<Icon icon={AddOutline} />}
          aria-label={t(`${i18nPrefix}.form.placeholder`)}
          disabled={!trimmedName || isNameTaken}
          onClick={handleAdd}
        />
      </div>
      {isNameTaken && (
        <span className="text-caption-sm-regular text-danger-primary">
          {t(`${i18nPrefix}.form.errors.name.integrity`)}
        </span>
      )}
    </div>
  );
});
