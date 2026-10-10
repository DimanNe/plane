/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// types
import type { IWorkspace } from "@plane/types";
// services
import { AppError } from "@/lib/errors";
import { APIService } from "@/services/api.service";

export class WorkspaceService extends APIService {
  /**
   * The API answers only a logged-in member of the workspace.
   */
  async retrieve(workspaceSlug: string, cookie: string): Promise<IWorkspace> {
    return this.get(`/api/workspaces/${workspaceSlug}/`, {
      headers: {
        Cookie: cookie,
      },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw new AppError(error, {
          context: { operation: "retrieve" },
        });
      });
  }
}
