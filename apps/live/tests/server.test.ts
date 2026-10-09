import type { Server as HttpServer } from "node:http";
import type { AddressInfo } from "node:net";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { HocusPocusServerManager } from "@/hocuspocus";
import { Server } from "@/server";
import { ApiStub } from "./helpers/api-stub";
import { Editor } from "./helpers/editor";

const api = vi.hoisted(() => ({ stub: undefined as unknown as ApiStub }));
vi.mock("@/env", () => ({
  env: {
    PORT: "0",
    LIVE_BASE_PATH: "/live",
    LIVE_SERVER_SECRET_KEY: "secret",
    CORS_ALLOWED_ORIGINS: "",
    COMPRESSION_LEVEL: 6,
    COMPRESSION_THRESHOLD: 5000,
    get API_BASE_URL() {
      return api.stub.origin;
    },
  },
}));
// The server runs without Redis: one instance needs it for nothing these tests look at.
vi.mock("@/redis", () => ({
  redisManager: { initialize: async () => {}, disconnect: async () => {}, getClient: () => null },
}));
vi.mock("@/extensions/redis", () => ({
  Redis: class {
    onAdminCommand() {}
    async broadcastToDocument() {
      return 0;
    }
  },
}));

const PAGE = "5b0d8a0e-4f0e-4f6c-9c57-6f4f2f1f8f11";

let server: Server;
let port: number;
let editor: Editor;

beforeAll(async () => {
  api.stub = new ApiStub();
  await api.stub.listen();
});

// A running server with an editor that has made a change the server has not stored yet
beforeEach(async () => {
  api.stub.reset();
  HocusPocusServerManager.resetInstance();
  server = new Server();
  await server.initialize();
  server.listen();
  const httpServer = (server as unknown as { httpServer: HttpServer }).httpServer;
  await new Promise((resolve) => httpServer.once("listening", resolve));
  port = (httpServer.address() as AddressInfo).port;
  editor = await Editor.open(
    `ws://127.0.0.1:${port}/live/collaboration?workspaceSlug=plane&documentType=workspace_page`,
    PAGE,
    JSON.stringify({ id: "user", cookie: "session-id=1" })
  );
  editor.type("change before the stop");
  await vi.waitFor(() => expect(editor.messages).toEqual(["saved", "unsaved"]));
});

afterEach(() => {
  vi.useRealTimers();
});

afterAll(async () => {
  await api.stub.close();
});

describe("Server.destroy", () => {
  it("stores the change that waits for its store, and stops listening", async () => {
    await server.destroy();

    expect(api.stub.stores.at(-1)?.description_html).toContain("change before the stop");
    await expect(fetch(`http://127.0.0.1:${port}/live/health`)).rejects.toThrow();
  });

  it("fails when the change cannot be stored", async () => {
    api.stub.beforeStore = () => Promise.reject(new Error("the API is down"));
    vi.useFakeTimers({ toFake: ["Date"] });

    const destroyed = server.destroy();
    await vi.waitFor(() => expect(api.stub.storeRequests).toBeGreaterThan(0));
    vi.setSystemTime(Date.now() + 24 * 3600000);

    await expect(destroyed).rejects.toThrow(`Documents not stored: ${PAGE}`);
    await editor.close();
  });
});
