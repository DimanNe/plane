/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// local imports
import { ModuleIssueQuickActions } from "../../quick-action-dropdowns";
import { BaseListRoot } from "../base-list-root";

export const ModuleListLayout = observer(function ModuleListLayout() {
  const { moduleId } = useParams();

  return <BaseListRoot QuickActions={ModuleIssueQuickActions} viewId={moduleId?.toString()} />;
});
