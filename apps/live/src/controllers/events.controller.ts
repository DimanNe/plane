/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Request } from "express";
import type { WebSocket } from "ws";
// plane imports
import { Controller, WebSocket as WSDecorator } from "@plane/decorators";
import { logger } from "@plane/logger";
import { changeEvents } from "@/change-events";
import { env } from "@/env";
import { WorkspaceService } from "@/services/workspace.service";

@Controller("/events")
export class EventsController {
  /**
   * A page asks for the changes of a workspace. The browser sends the session cookie with the
   * request, and would send it for the page of another site too. So the page must come from the
   * address the request was sent to, or from one of the configured origins.
   */
  @WSDecorator("/")
  async handleConnection(ws: WebSocket, req: Request) {
    try {
      const origin = req.headers.origin ?? "";
      const allowedOrigins = env.CORS_ALLOWED_ORIGINS.split(",").map((s) => s.trim());
      if (URL.parse(origin)?.host !== req.headers.host && !allowedOrigins.includes(origin))
        throw new Error(`origin ${origin}`);
      const workspaceService = new WorkspaceService();
      const workspace = await workspaceService.retrieve(String(req.query.workspaceSlug), req.headers.cookie ?? "");
      if (ws.readyState === ws.OPEN) changeEvents.add(ws, workspace.id);
    } catch (error) {
      logger.warn("EVENTS_CONTROLLER: Connection refused:", error);
      ws.close(1008);
    }
  }
}
