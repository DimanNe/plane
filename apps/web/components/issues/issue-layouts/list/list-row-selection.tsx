/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// hooks
import { useListRowSelection } from "@/hooks/use-list-row-selection";

/**
 * The selection of the List layout's rows, in a component of its own that draws nothing. Every press of an arrow
 * key moves the selection, and a component that reads it draws again: in the list itself that drew every group,
 * and every row of them, longer than a held key takes to repeat.
 */
export const ListRowSelection = observer(function ListRowSelection(props: Parameters<typeof useListRowSelection>[0]) {
  useListRowSelection(props);
  return null;
});
