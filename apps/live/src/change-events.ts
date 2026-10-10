/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type Redis from "ioredis";
import type { WebSocket } from "ws";
import { logger } from "@plane/logger";
import { redisManager } from "@/redis";

const CHANNEL = "plane:changes";
// Redis keeps nothing for a subscriber that is away. This message tells a page that changes may
// have been missed, and the page fetches again what it shows.
const RESYNC_MESSAGE = JSON.stringify({ resync: true });
// A page that hears nothing for longer than this takes its connection for dead and opens a new one.
const HEARTBEAT_MESSAGE = JSON.stringify({ heartbeat: true });
const HEARTBEAT_INTERVAL = 20_000;

/**
 * Sends the changes of records, which the API publishes on a Redis channel as the ids of each
 * changed row, on to the open pages of the workspace the row belongs to.
 */
class ChangeEvents {
  private workspaceIdBySocket = new Map<WebSocket, string>();
  private subscriber: Redis | undefined;
  private heartbeat: NodeJS.Timeout | undefined;

  start() {
    this.subscriber = redisManager.getClient()?.duplicate();
    // also after every reconnect, when the subscription is made again
    this.subscriber?.on("ready", () => this.send(RESYNC_MESSAGE));
    this.subscriber?.on("message", (_channel: string, message: string) => {
      const { resync, w: workspaceId } = JSON.parse(message) as { resync?: boolean; w?: string | null };
      this.send(message, resync ? undefined : workspaceId);
    });
    this.subscriber
      ?.subscribe(CHANNEL)
      .catch((error) => logger.error(`CHANGE_EVENTS: Failed to subscribe to ${CHANNEL}:`, error));
    this.heartbeat = setInterval(() => this.send(HEARTBEAT_MESSAGE), HEARTBEAT_INTERVAL);
  }

  /** Called when the socket may get the changes of the workspace: from here on it misses none. */
  add(socket: WebSocket, workspaceId: string) {
    this.workspaceIdBySocket.set(socket, workspaceId);
    socket.on("close", () => this.workspaceIdBySocket.delete(socket));
    socket.send(RESYNC_MESSAGE);
  }

  /** Node does not close these connections with the HTTP server, and waits for them when it closes. */
  stop() {
    clearInterval(this.heartbeat);
    this.subscriber?.disconnect();
    this.workspaceIdBySocket.forEach((_workspaceId, socket) => socket.terminate());
  }

  // To every socket when no workspace is given. A row that belongs to no workspace (null) goes to none.
  private send(message: string, workspaceId?: string | null) {
    this.workspaceIdBySocket.forEach((socketWorkspaceId, socket) => {
      if (workspaceId === undefined || workspaceId === socketWorkspaceId) socket.send(message);
    });
  }
}

export const changeEvents = new ChangeEvents();
