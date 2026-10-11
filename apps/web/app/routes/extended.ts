/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { layout, route } from "@react-router/dev/routes";
import type { RouteConfigEntry } from "@react-router/dev/routes";

export const extendedRoutes: RouteConfigEntry[] = [
  layout("./(all)/layout.tsx", [
    layout("./(all)/[workspaceSlug]/layout.tsx", [
      layout("./(all)/[workspaceSlug]/(projects)/layout.tsx", [
        // The short address of a project's work items: /<workspace>/<project identifier>, a layout after it, or
        // -<number> for a work item. A page of the workspace wins over it by its fixed first word.
        route(
          ":workspaceSlug/:workItemsAddress/:layout?",
          "./(all)/[workspaceSlug]/(projects)/[workItemsAddress]/page.tsx"
        ),
      ]),
    ]),
  ]),
];
