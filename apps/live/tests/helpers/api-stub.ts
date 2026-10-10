import * as http from "node:http";
import type { AddressInfo } from "node:net";
import { getBinaryDataFromDocumentEditorHTMLString } from "@plane/editor";

export type TStore = {
  description_binary: string;
  description_html: string;
  description_json: object;
  name?: string;
};

/**
 * Stands for the API as the live server uses it for the pages of the workspace "plane": it knows one
 * user, serves the stored document of any page and takes the stores of it. The user, whose cookie
 * is "session-id=1", is a member of the workspaces "plane" and "other".
 */
export class ApiStub {
  origin = "";
  // The document a page has before its first store
  storedBinary!: Uint8Array;
  // The stores the API took, and the number it was asked for
  stores!: TStore[];
  storeRequests!: number;
  // Runs before a store is taken. A test holds the store here, or throws to fail it.
  beforeStore!: () => Promise<void>;

  private binaries = new Map<string, Uint8Array>();
  private server = http.createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk: Buffer) => chunks.push(chunk));
    request.on("end", () => {
      void this.answer(request, Buffer.concat(chunks).toString(), response);
    });
  });

  constructor() {
    this.reset();
  }

  // Forgets the stores, and the pages are as they were before the first of them.
  reset() {
    this.storedBinary = getBinaryDataFromDocumentEditorHTMLString("<p>Stored</p>", "Stored title");
    this.stores = [];
    this.storeRequests = 0;
    this.beforeStore = async () => {};
    this.binaries.clear();
  }

  async listen() {
    await new Promise<void>((resolve) => this.server.listen(0, "127.0.0.1", resolve));
    this.origin = `http://127.0.0.1:${(this.server.address() as AddressInfo).port}`;
  }

  async close() {
    this.server.closeAllConnections();
    await new Promise((resolve) => this.server.close(resolve));
  }

  private async answer(request: http.IncomingMessage, body: string, response: http.ServerResponse) {
    const json = (status: number, data: object) =>
      response.writeHead(status, { "Content-Type": "application/json" }).end(JSON.stringify(data));
    const [, pageId, description] =
      /^\/api\/workspaces\/plane\/pages\/([^/]+)\/(description\/)?$/.exec(request.url ?? "") ?? [];
    const [, workspaceSlug] = /^\/api\/workspaces\/([^/]+)\/$/.exec(request.url ?? "") ?? [];
    if (request.url === "/api/users/me/") {
      json(200, { id: "user", display_name: "User" });
    } else if (workspaceSlug && request.headers.cookie !== "session-id=1") {
      json(401, {});
    } else if (workspaceSlug === "plane" || workspaceSlug === "other") {
      json(200, { id: `id-of-${workspaceSlug}`, slug: workspaceSlug });
    } else if (!pageId) {
      json(404, {});
    } else if (!description) {
      json(200, { id: pageId, name: "Stored title", description_html: "<p>Stored</p>" });
    } else if (request.method === "GET") {
      response
        .writeHead(200, { "Content-Type": "application/octet-stream" })
        .end(this.binaries.get(pageId) ?? this.storedBinary);
    } else {
      this.storeRequests += 1;
      try {
        await this.beforeStore();
      } catch {
        json(500, {});
        return;
      }
      const store = JSON.parse(body) as TStore;
      this.stores.push(store);
      this.binaries.set(pageId, Buffer.from(store.description_binary, "base64"));
      json(200, { message: "Updated successfully" });
    }
  }
}
