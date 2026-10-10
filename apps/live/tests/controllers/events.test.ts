import type { Server as HttpServer } from "node:http";
import type { AddressInfo } from "node:net";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { WebSocket } from "ws";
import { HocusPocusServerManager } from "@/hocuspocus";
import { Server } from "@/server";
import { ApiStub } from "../helpers/api-stub";

const api = vi.hoisted(() => ({ stub: undefined as unknown as ApiStub }));
// The subscriber connection of the live server: a test publishes by emitting "message" on it.
const subscriber = await vi.hoisted(async () => {
  const { EventEmitter } = await import("node:events");
  return Object.assign(new EventEmitter(), { subscribe: async () => {}, disconnect: () => {} });
});
vi.mock("@/env", () => ({
  env: {
    PORT: "0",
    LIVE_BASE_PATH: "/live",
    LIVE_SERVER_SECRET_KEY: "secret",
    CORS_ALLOWED_ORIGINS: "http://plane.test",
    COMPRESSION_LEVEL: 6,
    COMPRESSION_THRESHOLD: 5000,
    get API_BASE_URL() {
      return api.stub.origin;
    },
  },
}));
vi.mock("@/redis", () => ({
  redisManager: {
    initialize: async () => {},
    disconnect: async () => {},
    getClient: () => ({ duplicate: () => subscriber }),
  },
}));
vi.mock("@/extensions/redis", () => ({
  Redis: class {
    onAdminCommand() {}
  },
}));

const MEMBER = { origin: "http://plane.test", cookie: "session-id=1" };
const RESYNC = { resync: true };
const CHANGE = { t: "issues", op: "U", id: "work-item", w: "id-of-plane", p: "project", i: null };

let server: Server;
let port: number;
let stopped: Promise<void> | undefined;
const stopServer = () => (stopped ??= server.destroy());

/** A browser page that asks for the changes of a workspace */
const openPage = (workspaceSlug: string, headers: Record<string, string> = MEMBER) => {
  const socket = new WebSocket(`ws://127.0.0.1:${port}/live/events?workspaceSlug=${workspaceSlug}`, { headers });
  const messages: object[] = [];
  socket.on("message", (data: Buffer) => messages.push(JSON.parse(data.toString())));
  return { messages, closeCode: new Promise<number>((resolve) => socket.once("close", resolve)) };
};

const publish = (message: object) => subscriber.emit("message", "plane:changes", JSON.stringify(message));

beforeAll(async () => {
  api.stub = new ApiStub();
  await api.stub.listen();
});

beforeEach(async () => {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  HocusPocusServerManager.resetInstance();
  server = new Server();
  stopped = undefined;
  await server.initialize();
  server.listen();
  const httpServer = (server as unknown as { httpServer: HttpServer }).httpServer;
  await new Promise((resolve) => httpServer.once("listening", resolve));
  port = (httpServer.address() as AddressInfo).port;
});

afterEach(async () => {
  await stopServer();
  subscriber.removeAllListeners();
  vi.useRealTimers();
});

afterAll(async () => {
  await api.stub.close();
});

describe("/live/events", () => {
  it("tells a page to fetch what it shows as soon as it gets the changes of its workspace", async () => {
    const page = openPage("plane");

    await vi.waitFor(() => expect(page.messages).toEqual([RESYNC]));
  });

  it("takes a page that was served from its own address, whatever origins are configured", async () => {
    const page = openPage("plane", { ...MEMBER, origin: `http://127.0.0.1:${port}` });

    await vi.waitFor(() => expect(page.messages).toEqual([RESYNC]));
  });

  it("sends a change to the pages of its workspace and to no other", async () => {
    const page = openPage("plane");
    const pageOfOtherWorkspace = openPage("other");
    await vi.waitFor(() => expect([page.messages, pageOfOtherWorkspace.messages]).toEqual([[RESYNC], [RESYNC]]));

    publish(CHANGE);
    // of a row that belongs to no workspace, such as a user's API token
    publish({ ...CHANGE, w: null });
    // the resync of the relay goes to every page, and tells here that the change before it was not sent
    publish(RESYNC);

    await vi.waitFor(() =>
      expect([page.messages, pageOfOtherWorkspace.messages]).toEqual([
        [RESYNC, CHANGE, RESYNC],
        [RESYNC, RESYNC],
      ])
    );
  });

  it("tells every page to fetch again when its Redis subscription was made again", async () => {
    const page = openPage("plane");
    await vi.waitFor(() => expect(page.messages).toEqual([RESYNC]));

    subscriber.emit("ready");

    await vi.waitFor(() => expect(page.messages).toEqual([RESYNC, RESYNC]));
  });

  it("sends a heartbeat at its interval", async () => {
    const page = openPage("plane");
    await vi.waitFor(() => expect(page.messages).toEqual([RESYNC]));

    vi.advanceTimersByTime(20_000);

    await vi.waitFor(() => expect(page.messages).toEqual([RESYNC, { heartbeat: true }]));
  });

  it.each([
    ["no cookie", "plane", { origin: MEMBER.origin }],
    ["the cookie of no session", "plane", { ...MEMBER, cookie: "session-id=2" }],
    ["a workspace the user is not a member of", "foreign", MEMBER],
    ["the page of another site", "plane", { ...MEMBER, origin: "http://other-site.test" }],
  ])("closes a connection with %s, and sends it nothing", async (_name, workspaceSlug, headers) => {
    const page = openPage(workspaceSlug, headers);

    expect([await page.closeCode, page.messages]).toEqual([1008, []]);
  });

  it("stops while a page is connected, and closes its connection", async () => {
    const page = openPage("plane");
    await vi.waitFor(() => expect(page.messages).toEqual([RESYNC]));

    await stopServer();

    expect(await page.closeCode).toBe(1006);
  });
});
