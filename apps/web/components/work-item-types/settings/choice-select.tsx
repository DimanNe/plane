/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { Select } from "@plane/blocks/select";

export type TChoice = { key: string; label: string; icon?: React.ReactNode };

type Props = {
  choices: TChoice[];
  value: string | null;
  onChange: (key: string) => void;
  placeholder?: string;
  disabled?: boolean;
};

/** A form field that takes one of a few fixed choices. */
export function ChoiceSelect(props: Props) {
  const { choices, value, onChange, placeholder, disabled } = props;

  return (
    <Select<TChoice>
      getValues={() => choices}
      value={choices.find((choice) => choice.key === value) ?? null}
      onChange={(key) => {
        if (key) onChange(key);
      }}
      getOptionValue={(choice) => choice.key}
      getOptionLabel={(choice) => choice.label}
      getOptionIcon={(choice) => choice.icon}
      placeholder={placeholder}
      disabled={disabled}
      showSearch={false}
      pinSelected={false}
      contentSizing="anchor"
    >
      <Select.Trigger variant="select-md" className="w-full">
        <Select.Value />
      </Select.Trigger>
    </Select>
  );
}
