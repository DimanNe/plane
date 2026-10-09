import * as http from "node:http";
import type { AddressInfo } from "node:net";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { getPageService } from "@/services/page/handler";
import { ProjectPageService } from "@/services/page/project-page.service";
import { WorkspacePageService } from "@/services/page/workspace-page.service";
import type { HocusPocusServerContext, TDocumentTypes } from "@/types";

const state = vi.hoisted(() => ({ apiOrigin: "" }));
vi.mock("@/env", () => ({
  env: {
    get API_BASE_URL() {
      return state.apiOrigin;
    },
  },
}));

const CONTEXT: HocusPocusServerContext = {
  documentType: "project_page",
  workspaceSlug: "plane",
  projectId: "ffcb7c13-eb54-43d7-a3b0-d6cbd3b8a42e",
  cookie: "session-id=1",
  userId: "",
};

// Answers every request as the API answers an image request: with a storage link on the host of the request.
let api: http.Server;

beforeAll(async () => {
  api = http.createServer((req, res) => {
    res.writeHead(302, { Location: `http://${req.headers.host}/uploads/image.png` }).end();
  });
  await new Promise<void>((resolve) => api.listen(0, "127.0.0.1", resolve));
  state.apiOrigin = `http://127.0.0.1:${(api.address() as AddressInfo).port}`;
});

afterAll(() => {
  api.close();
});

describe("getPageService", () => {
  it.each([
    { documentType: "project_page", expected: ProjectPageService },
    { documentType: "workspace_page", expected: WorkspacePageService },
  ] as const)("serves a $documentType document", ({ documentType, expected }) => {
    expect(getPageService(documentType, CONTEXT)).toBeInstanceOf(expected);
  });

  it.each([
    { name: "an unknown document type", documentType: "unknown", context: CONTEXT },
    {
      name: "a project page without a project",
      documentType: "project_page",
      context: { ...CONTEXT, projectId: null },
    },
    {
      name: "a project page without a workspace",
      documentType: "project_page",
      context: { ...CONTEXT, workspaceSlug: null },
    },
    {
      name: "a workspace page without a workspace",
      documentType: "workspace_page",
      context: { ...CONTEXT, workspaceSlug: null },
    },
    { name: "a workspace page without a cookie", documentType: "workspace_page", context: { ...CONTEXT, cookie: "" } },
  ])("refuses $name", ({ documentType, context }) => {
    expect(() => getPageService(documentType as TDocumentTypes, context)).toThrow();
  });
});

describe("PageCoreService.resolveImageAssetUrl", () => {
  it("asks the API for a storage link on the host the browser uses", async () => {
    const service = getPageService("workspace_page", CONTEXT);

    const url = await service.resolveImageAssetUrl("plane", "asset-id", null, "plane.example:8080");

    expect(url).toBe("http://plane.example:8080/uploads/image.png");
  });
});
