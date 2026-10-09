/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { EWorkItemPropertyRelationType, EWorkItemPropertyType } from "@plane/types";
import type { TWorkItemProperty, TWorkItemPropertyTypeKey } from "@plane/types";

export const WORK_ITEM_PROPERTY_TYPES: Record<
  TWorkItemPropertyTypeKey,
  { i18n_label: string } & Pick<TWorkItemProperty, "property_type" | "relation_type">
> = {
  TEXT: {
    i18n_label: "work_item_types.settings.properties.property_type.text.label",
    property_type: EWorkItemPropertyType.TEXT,
    relation_type: null,
  },
  DECIMAL: {
    i18n_label: "work_item_types.settings.properties.property_type.number.label",
    property_type: EWorkItemPropertyType.DECIMAL,
    relation_type: null,
  },
  OPTION: {
    i18n_label: "work_item_types.settings.properties.property_type.dropdown.label",
    property_type: EWorkItemPropertyType.OPTION,
    relation_type: null,
  },
  BOOLEAN: {
    i18n_label: "work_item_types.settings.properties.property_type.boolean.label",
    property_type: EWorkItemPropertyType.BOOLEAN,
    relation_type: null,
  },
  DATETIME: {
    i18n_label: "work_item_types.settings.properties.property_type.date.label",
    property_type: EWorkItemPropertyType.DATETIME,
    relation_type: null,
  },
  RELATION_USER: {
    i18n_label: "work_item_types.settings.properties.property_type.member_picker.label",
    property_type: EWorkItemPropertyType.RELATION,
    relation_type: EWorkItemPropertyRelationType.USER,
  },
  RELATION_RICH_TEXT: {
    i18n_label: "work_item_types.settings.properties.property_type.rich_text.label",
    property_type: EWorkItemPropertyType.RELATION,
    relation_type: EWorkItemPropertyRelationType.RICH_TEXT,
  },
  URL: {
    i18n_label: "work_item_types.settings.properties.property_type.url.label",
    property_type: EWorkItemPropertyType.URL,
    relation_type: null,
  },
  FORMULA: {
    i18n_label: "work_item_types.settings.properties.property_type.formula.label",
    property_type: EWorkItemPropertyType.FORMULA,
    relation_type: null,
  },
  CASCADING: {
    i18n_label: "work_item_types.settings.properties.property_type.cascading.label",
    property_type: EWorkItemPropertyType.CASCADING,
    relation_type: null,
  },
};

export const WORK_ITEM_PROPERTY_TEXT_FORMATS: { key: string; i18n_label: string }[] = [
  { key: "single-line", i18n_label: "work_item_types.settings.properties.attributes.text.single_line.label" },
  { key: "multi-line", i18n_label: "work_item_types.settings.properties.attributes.text.multi_line.label" },
  { key: "readonly", i18n_label: "work_item_types.settings.properties.attributes.text.readonly.label" },
];

// date-fns formats
export const WORK_ITEM_PROPERTY_DATE_FORMATS = ["MMM dd, yyyy", "dd/MM/yyyy", "MM/dd/yyyy", "yyyy/MM/dd"];

export const WORK_ITEM_PROPERTY_MIN_LEVELS = 2;
export const WORK_ITEM_PROPERTY_MAX_LEVELS = 4;

// The key of a property in display properties is this prefix and the property id.
export const WORK_ITEM_PROPERTY_KEY_PREFIX = "custom_properties__";
