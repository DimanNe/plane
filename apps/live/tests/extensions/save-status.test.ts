import type { Extension } from "@hocuspocus/server";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import * as Y from "yjs";
import {
  getAllDocumentFormatsFromDocumentEditorBinaryData,
  getBinaryDataFromDocumentEditorHTMLString,
} from "@plane/editor";
import { ApiStub } from "../helpers/api-stub";
import { startCollaboration } from "../helpers/collaboration";

const api = vi.hoisted(() => ({ stub: undefined as unknown as ApiStub }));
vi.mock("@/env", () => ({
  env: {
    get API_BASE_URL() {
      return api.stub.origin;
    },
  },
}));

const PAGE = "5b0d8a0e-4f0e-4f6c-9c57-6f4f2f1f8f11";
// A debounce no test waits for: the store of a change runs only when something else starts it.
const NEVER = 3600000;

let collaboration: Awaited<ReturnType<typeof startCollaboration>>;

const start = async (configuration: Parameters<typeof startCollaboration>[0]) => {
  collaboration = await startCollaboration(configuration);
  return collaboration;
};

// The API holds every store from now on. Returns the functions that let them go on, in the order of the stores.
const holdStores = () => {
  const releases: (() => void)[] = [];
  api.stub.beforeStore = () => new Promise<void>((resolve) => releases.push(resolve));
  return releases;
};

// Lets the held stores go on, and the API takes the stores after them at once.
const releaseStores = (releases: (() => void)[]) => {
  api.stub.beforeStore = async () => {};
  releases.forEach((release) => release());
};

const pause = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const getStoredHTML = () => api.stub.stores.at(-1)?.description_html ?? "";

// Stands for the lock of the Redis extension: a store of a document does not run beside another store
// of it, and Hocuspocus drops the store that is refused, with no error.
const createStoreLock = (): Extension => {
  const storing = new Set<string>();
  return {
    priority: 1000,
    async onStoreDocument({ documentName }) {
      if (storing.has(documentName)) return Promise.reject();
      storing.add(documentName);
    },
    async afterStoreDocument({ documentName }) {
      storing.delete(documentName);
    },
  };
};

beforeAll(async () => {
  api.stub = new ApiStub();
  await api.stub.listen();
});

beforeEach(() => {
  api.stub.reset();
});

afterEach(() => {
  vi.useRealTimers();
  collaboration.close();
});

afterAll(async () => {
  await api.stub.close();
});

describe("save status of a document", () => {
  it("is told to the editors once when changes begin and once when a store holds the latest change", async () => {
    const { openEditor } = await start({ debounce: 20 });
    const editor = await openEditor(PAGE);

    editor.type("first");
    editor.type("second");

    await vi.waitFor(() => expect(editor.messages).toEqual(["saved", "unsaved", "saved"]));
    expect(getStoredHTML()).toContain("second");
  });

  it("stays unsaved when a change arrives while a store runs, until a store holds that change", async () => {
    const { openEditor } = await start({ debounce: 0 });
    const editor = await openEditor(PAGE);
    const heldStores = holdStores();
    editor.type("first");
    await vi.waitFor(() => expect(heldStores).toHaveLength(1));
    editor.type("second");
    await vi.waitFor(() => expect(heldStores).toHaveLength(2));

    heldStores[0]!();
    await vi.waitFor(() => expect(api.stub.stores).toHaveLength(1));
    await pause(50);
    const messagesAfterFirstStore = [...editor.messages];
    heldStores[1]!();

    await vi.waitFor(() => expect(editor.messages).toEqual(["saved", "unsaved", "saved"]));
    expect(messagesAfterFirstStore).toEqual(["saved", "unsaved"]);
  });

  it.each([
    { name: "saved for a stored document", change: false, expected: "saved" },
    { name: "unsaved for a document with a change no store holds", change: true, expected: "unsaved" },
  ])("is answered as $name to an editor that asks", async ({ change, expected }) => {
    const { openEditor } = await start({ debounce: NEVER });
    const editor = await openEditor(PAGE);
    if (change) {
      editor.type("change");
      await vi.waitFor(() => expect(editor.messages).toEqual(["saved", "unsaved"]));
    }
    const asking = await openEditor(PAGE);

    expect(asking.messages).toEqual([expected]);
  });

  it("is saved for a document loaded again after a store completed when the document was unloaded", async () => {
    const { hocuspocus, openEditor } = await start({ debounce: 0 });
    const editor = await openEditor(PAGE);
    const heldStores = holdStores();
    editor.type("change");
    await vi.waitFor(() => expect(heldStores).toHaveLength(1));
    await editor.close();
    await vi.waitFor(() => expect(hocuspocus.documents.size).toBe(0));
    releaseStores(heldStores);
    await vi.waitFor(() => expect(api.stub.stores).toHaveLength(1));

    const editorOfReloadedDocument = await openEditor(PAGE);

    expect(editorOfReloadedDocument.messages).toEqual(["saved"]);
  });

  it("counts a change when it is made, though an extension before this one delays the change hook", async () => {
    let releaseChangeHook: (() => void) | undefined;
    const delayingExtension: Extension = {
      priority: 1000,
      onChange: () => new Promise<void>((resolve) => (releaseChangeHook = resolve)),
    };
    const { openEditor } = await start({ debounce: 0, extensions: [delayingExtension] });
    const editor = await openEditor(PAGE);

    editor.type("change");
    await vi.waitFor(() => expect(api.stub.stores).toHaveLength(1));
    releaseChangeHook?.();
    await pause(50);
    editor.requestSaveStatus();

    await vi.waitFor(() => expect(editor.messages).toEqual(["saved", "unsaved", "saved", "saved"]));
  });
});

describe("store of a document", () => {
  it.each([
    { name: "the title of the document as the name of the page", title: "Title", expected: "Title" },
    { name: "no name for a document that has no title", title: undefined, expected: undefined },
  ])("sends $name", async ({ title, expected }) => {
    api.stub.storedBinary = getBinaryDataFromDocumentEditorHTMLString("<p>Stored</p>", title);
    const { openEditor } = await start({ debounce: 0 });
    const editor = await openEditor(PAGE);

    editor.type("change");

    await vi.waitFor(() => expect(api.stub.stores).toHaveLength(1));
    expect(api.stub.stores[0]!.name).toBe(expected);
  });
});

describe("storeLoadedDocuments", () => {
  it("stores a change whose store has not run yet", async () => {
    const { database, hocuspocus, openEditor } = await start({ debounce: NEVER });
    const editor = await openEditor(PAGE);
    editor.type("pending change");
    await vi.waitFor(() => expect(editor.messages).toEqual(["saved", "unsaved"]));

    await database.storeLoadedDocuments(hocuspocus);

    expect(getStoredHTML()).toContain("pending change");
  });

  it("waits for a store that runs", async () => {
    const { database, hocuspocus, openEditor } = await start({ debounce: 0 });
    const editor = await openEditor(PAGE);
    const heldStores = holdStores();
    editor.type("change");
    await vi.waitFor(() => expect(heldStores).toHaveLength(1));

    let isStored = false;
    const stored = database.storeLoadedDocuments(hocuspocus).then(() => (isStored = true));
    await pause(300);
    const wasStoredWhileTheStoreRan = isStored;
    releaseStores(heldStores);
    await stored;

    expect({ wasStoredWhileTheStoreRan, stores: api.stub.stores.length }).toEqual({
      wasStoredWhileTheStoreRan: false,
      stores: 1,
    });
  });

  it("stores a change made while a store ran, whose own store was refused beside that one", async () => {
    const { database, hocuspocus, openEditor } = await start({ debounce: 0, extensions: [createStoreLock()] });
    const editor = await openEditor(PAGE);
    const heldStores = holdStores();
    editor.type("first");
    await vi.waitFor(() => expect(heldStores).toHaveLength(1));
    editor.type("second");
    await pause(50);

    const stored = database.storeLoadedDocuments(hocuspocus);
    await pause(300);
    releaseStores(heldStores);
    await stored;

    expect({ stores: api.stub.stores.length, html: getStoredHTML() }).toEqual({
      stores: 2,
      html: expect.stringContaining("second"),
    });
  });

  it("fails when a document is not stored in time", async () => {
    const { database, hocuspocus, openEditor } = await start({ debounce: NEVER });
    const editor = await openEditor(PAGE);
    editor.type("change");
    await vi.waitFor(() => expect(editor.messages).toEqual(["saved", "unsaved"]));
    api.stub.beforeStore = () => Promise.reject(new Error("the API is down"));
    vi.useFakeTimers({ toFake: ["Date"] });

    const stored = database.storeLoadedDocuments(hocuspocus);
    await vi.waitFor(() => expect(api.stub.storeRequests).toBeGreaterThan(0));
    vi.setSystemTime(Date.now() + 24 * 3600000);

    await expect(stored).rejects.toThrow(`Documents not stored: ${PAGE}`);
  });

  it("closes the documents to further changes of their editors", async () => {
    const { database, hocuspocus, openEditor } = await start({ debounce: NEVER });
    const editor = await openEditor(PAGE);
    const getHTML = () =>
      getAllDocumentFormatsFromDocumentEditorBinaryData(Y.encodeStateAsUpdate(hocuspocus.documents.get(PAGE)!), false)
        .contentHTML;

    await database.storeLoadedDocuments(hocuspocus);
    editor.type("late change");
    await pause(100);

    expect(getHTML()).not.toContain("late change");
  });
});
