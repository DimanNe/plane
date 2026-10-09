import { Hocuspocus } from "@hocuspocus/server";
import type { Request, Response } from "express";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import * as Y from "yjs";
import {
  getAllDocumentFormatsFromDocumentEditorBinaryData,
  getBinaryDataFromDocumentEditorHTMLString,
} from "@plane/editor";
import { PageContentController } from "@/controllers/page-content.controller";
import { ApiStub } from "../helpers/api-stub";
import { startCollaboration } from "../helpers/collaboration";

const api = vi.hoisted(() => ({ stub: undefined as unknown as ApiStub }));
vi.mock("@/env", () => ({
  env: {
    LIVE_SERVER_SECRET_KEY: "secret",
    get API_BASE_URL() {
      return api.stub.origin;
    },
  },
}));

const PAGE_ID = "5b0d8a0e-4f0e-4f6c-9c57-6f4f2f1f8f11";

type TContent = { name: string; description_html: string };

const getBinary = (content: TContent) =>
  getBinaryDataFromDocumentEditorHTMLString(content.description_html, content.name);

// The name and the description as an editor shows a document
const getContent = (binary: Uint8Array): TContent => {
  const { contentHTML, titleHTML } = getAllDocumentFormatsFromDocumentEditorBinaryData(binary, true);
  return { name: titleHTML ?? "", description_html: contentHTML };
};

const replacePageContent = async (server: Hocuspocus, body: Record<string, unknown>) => {
  const response = { statusCode: 0, body: {} as Record<string, unknown> };
  const res = {
    status: (statusCode: number) => {
      response.statusCode = statusCode;
      return res;
    },
    json: (payload: Record<string, unknown>) => {
      response.body = payload;
      return res;
    },
  };
  await new PageContentController(server).replacePageContent({ body } as Request, res as unknown as Response);
  return response;
};

const OLD: TContent = { name: "Old name", description_html: "<p>Old description</p>" };
const NEW: TContent = { name: "New name", description_html: "<p>New description</p>" };

beforeAll(async () => {
  api.stub = new ApiStub();
  await api.stub.listen();
});

beforeEach(() => {
  api.stub.reset();
});

afterAll(async () => {
  await api.stub.close();
});

describe("PageContentController", () => {
  it.each([
    { name: "the name and the description", change: NEW, expected: NEW },
    { name: "the name alone", change: { name: NEW.name }, expected: { ...OLD, name: NEW.name } },
    {
      name: "the description alone",
      change: { description_html: NEW.description_html },
      expected: { ...OLD, description_html: NEW.description_html },
    },
  ])("replaces $name in the stored document of a page that is not open", async ({ change, expected }) => {
    const storedBinary = getBinary(OLD);

    const response = await replacePageContent(new Hocuspocus(), {
      page_id: PAGE_ID,
      description_binary: Buffer.from(storedBinary).toString("base64"),
      ...change,
    });

    const returnedBinary = Buffer.from(response.body.description_binary as string, "base64");
    // An editor that kept the stored document merges the returned one into it
    const editorDocument = new Y.Doc();
    Y.applyUpdate(editorDocument, storedBinary);
    Y.applyUpdate(editorDocument, returnedBinary);
    expect({
      statusCode: response.statusCode,
      description_html: response.body.description_html,
      returned: getContent(returnedBinary),
      editor: getContent(Y.encodeStateAsUpdate(editorDocument)),
    }).toEqual({
      statusCode: 200,
      description_html: getContent(getBinary(expected)).description_html,
      returned: getContent(getBinary(expected)),
      editor: getContent(getBinary(expected)),
    });
  });

  it("replaces the content inside the loaded document of a page that is open, and it is stored as an editor's change", async () => {
    api.stub.storedBinary = getBinary(OLD);
    const collaboration = await startCollaboration({ debounce: 20 });
    const editor = await collaboration.openEditor(PAGE_ID);

    const response = await replacePageContent(collaboration.hocuspocus, {
      page_id: PAGE_ID,
      description_binary: "",
      ...NEW,
    });

    await vi.waitFor(() => expect(api.stub.stores).toHaveLength(1));
    const loadedDocument = collaboration.hocuspocus.documents.get(PAGE_ID)!;
    expect({
      loaded: getContent(Y.encodeStateAsUpdate(loadedDocument)),
      returned: getContent(Buffer.from(response.body.description_binary as string, "base64")),
      stored: { name: api.stub.stores[0]!.name, description_html: api.stub.stores[0]!.description_html },
    }).toEqual({
      loaded: getContent(getBinary(NEW)),
      returned: getContent(getBinary(NEW)),
      stored: getContent(getBinary(NEW)),
    });
    await vi.waitFor(() => expect(editor.messages).toEqual(["saved", "unsaved", "saved"]));
    collaboration.close();
  });

  it("answers with an error when the change cannot be made", async () => {
    const response = await replacePageContent(new Hocuspocus(), {
      page_id: PAGE_ID,
      description_binary: Buffer.from("not a document").toString("base64"),
      ...NEW,
    });

    expect(response).toEqual({ statusCode: 500, body: { message: "Internal server error." } });
  });
});
