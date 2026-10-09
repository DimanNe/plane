/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "./common";

export enum EWorkItemPropertyType {
  TEXT = "TEXT",
  DECIMAL = "DECIMAL",
  OPTION = "OPTION",
  BOOLEAN = "BOOLEAN",
  DATETIME = "DATETIME",
  RELATION = "RELATION",
  URL = "URL",
  FORMULA = "FORMULA",
  CASCADING = "CASCADING",
}

export enum EWorkItemPropertyRelationType {
  USER = "USER",
  RICH_TEXT = "RICH_TEXT",
}

export type TWorkItemType = {
  id: string;
  name: string;
  description: string;
  logo_props: TLogoProps;
  is_default: boolean;
  is_active: boolean;
};

export type TWorkItemPropertyOption = {
  id: string;
  name: string;
  logo_props: TLogoProps;
  sort_order: number;
  is_default: boolean;
  // the option of the level above, for an option of a cascading property below its first level
  parent: string | null;
  // what the options under this one are called in place of the name of their level
  sub_level_label: string;
  // present only when a single option is retrieved
  work_item_count?: number;
};

export type TWorkItemPropertyLevel = {
  name: string;
  is_required: boolean;
};

export type TWorkItemPropertySettings = {
  // TEXT: "single-line" | "multi-line" | "readonly", DATETIME: a date-fns format
  display_format?: string;
  // FORMULA
  expression?: string;
  // CASCADING: two to four levels
  levels?: TWorkItemPropertyLevel[];
};

export type TWorkItemProperty = {
  id: string;
  project: string;
  issue_type: string;
  display_name: string;
  description: string;
  sort_order: number;
  property_type: EWorkItemPropertyType;
  relation_type: EWorkItemPropertyRelationType | null;
  is_required: boolean;
  is_active: boolean;
  is_multi: boolean;
  default_value: string[];
  settings: TWorkItemPropertySettings;
  options: TWorkItemPropertyOption[];
};

export type TWorkItemPropertyOptionPayload = Partial<
  Pick<TWorkItemPropertyOption, "name" | "logo_props" | "is_default" | "parent" | "sub_level_label">
>;

// options are accepted only when the property is created; afterwards they have endpoints of their own
export type TWorkItemPropertyPayload = Partial<Omit<TWorkItemProperty, "id" | "project" | "issue_type" | "options">> & {
  options?: TWorkItemPropertyOptionPayload[];
};

// text, URL and rich text (HTML) are strings, a date is "YYYY-MM-DD", an option or a member is its id;
// the value of a cascading property is the ids of the options chosen on its levels, first level first
export type TWorkItemPropertyValue = string | number | boolean | string[] | null;

// identifies what the "Property type" dropdown offers: RELATION is offered once per relation_type
export type TWorkItemPropertyTypeKey =
  | Exclude<`${EWorkItemPropertyType}`, "RELATION">
  | `RELATION_${EWorkItemPropertyRelationType}`;
