import type { AddressInfo } from "node:net";
import { Hocuspocus } from "@hocuspocus/server";
import type { Configuration } from "@hocuspocus/server";
import { WebSocketServer } from "ws";
import { DatabaseWithSaveStatus } from "@/extensions/save-status";
import type { HocusPocusServerContext } from "@/types";
import { Editor } from "./editor";

// What the live server keeps of an authenticated editor of a workspace page
const CONTEXT: HocusPocusServerContext = {
  documentType: "workspace_page",
  workspaceSlug: "plane",
  projectId: null,
  cookie: "session-id=1",
  userId: "user",
};

/**
 * A Hocuspocus server with the extension that stores documents, reachable by editors over
 * WebSocket. The other extensions of the live server are left out, the given ones are added.
 */
export const startCollaboration = async (configuration: Partial<Configuration>) => {
  const database = new DatabaseWithSaveStatus();
  const hocuspocus = new Hocuspocus({
    ...configuration,
    extensions: [database, ...(configuration.extensions ?? [])],
  });
  const sockets = new WebSocketServer({ port: 0, host: "127.0.0.1" });
  sockets.on("connection", (socket, request) => hocuspocus.handleConnection(socket, request, CONTEXT));
  await new Promise((resolve) => sockets.once("listening", resolve));
  const url = `ws://127.0.0.1:${(sockets.address() as AddressInfo).port}`;
  return {
    database,
    hocuspocus,
    openEditor: (documentName: string) => Editor.open(url, documentName),
    close: () => {
      sockets.clients.forEach((socket) => socket.terminate());
      sockets.close();
    },
  };
};
