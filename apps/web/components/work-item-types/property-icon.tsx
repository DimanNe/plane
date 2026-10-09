/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { FC } from "react";
import {
  BooleanOutline,
  CalendarOutline,
  DropdownOutline,
  FormulaOutline,
  HashOutline,
  HierarchyOutline,
  LinkOutline,
  MembersOutline,
  PagesOutline,
  TextOutline,
} from "@makeplane/propel/icons";
// plane imports
import type { ISvgIcons } from "@plane/blocks/icons";
import type { TWorkItemPropertyTypeKey } from "@plane/types";

export const WORK_ITEM_PROPERTY_TYPE_ICONS: Record<TWorkItemPropertyTypeKey, FC<ISvgIcons>> = {
  TEXT: TextOutline,
  DECIMAL: HashOutline,
  OPTION: DropdownOutline,
  BOOLEAN: BooleanOutline,
  DATETIME: CalendarOutline,
  RELATION_USER: MembersOutline,
  RELATION_RICH_TEXT: PagesOutline,
  URL: LinkOutline,
  FORMULA: FormulaOutline,
  CASCADING: HierarchyOutline,
};
