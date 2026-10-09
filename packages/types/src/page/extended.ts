/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TPaginationInfo } from "../common";
import type { TPage } from "./core";

export type TPageExtended = {
  parent_id?: string | null;
  // wiki pages only
  collection_id?: string | null;
  sort_order?: number;
};

export type TWorkspacePagesResponse = TPaginationInfo & {
  results: TPage[];
};
