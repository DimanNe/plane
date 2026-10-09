/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "../common";
import type { EPageAccess } from "../enums";

export type TPageCollection = {
  id: string;
  name: string;
  access: EPageAccess;
  owned_by_id: string;
  is_default: boolean;
  logo_props: TLogoProps | undefined;
  sort_order: number;
};
