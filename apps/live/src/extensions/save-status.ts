/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type {
  Document,
  Hocuspocus,
  afterLoadDocumentPayload,
  onChangePayload,
  onStatelessPayload,
} from "@hocuspocus/server";
import { SAVE_STATUS } from "@plane/editor";
// lib
import { AppError } from "@/lib/errors";
// types
import type { HocusPocusServerContext } from "@/types";
import { Database } from "./database";

type TSaveState = {
  // Of the editor whose change was stored last, or who loaded the document. A store at shutdown runs as that editor.
  context: HocusPocusServerContext;
  // The updates of the document since it was loaded
  changes: number;
  // `changes` at the start of the store that completed last
  storedChanges: number;
  runningStores: number;
};

/**
 * The process can be killed at any moment, and a change that is only in its memory is then lost.
 * This is the Database extension that also knows, for each loaded document, whether the database has
 * its latest change. It tells the editors, which show "Saved" or "Unsaved changes", and at shutdown
 * it stores what is left, so that the process exits cleanly only when nothing is lost.
 *
 * The state is kept with the Document object and not by the name of the document: a store can
 * complete after its document was unloaded, and must not count for the one loaded next.
 */
export class DatabaseWithSaveStatus extends Database {
  private saveStates = new WeakMap<Document, TSaveState>();

  async afterLoadDocument({ document, context }: afterLoadDocumentPayload) {
    const state: TSaveState = { context, changes: 0, storedChanges: 0, runningStores: 0 };
    this.saveStates.set(document, state);
    // Counted in the update itself. The onChange hook runs later, after the awaited hooks of the
    // extensions before this one, when a store can already hold the update.
    document.on("update", () => {
      const wasSaved = state.changes === state.storedChanges;
      state.changes += 1;
      if (wasSaved) {
        document.broadcastStateless(SAVE_STATUS.unsaved);
      }
    });
  }

  async onStoreDocument(data: onChangePayload) {
    const state = this.saveStates.get(data.document)!;
    // The store reads the document before it waits for anything, so this is the change it stores.
    const changes = state.changes;
    state.context = data.context;
    state.runningStores += 1;
    try {
      await super.onStoreDocument(data);
    } finally {
      state.runningStores -= 1;
    }
    const wasSaved = state.changes === state.storedChanges;
    state.storedChanges = changes;
    const isSaved = state.changes === state.storedChanges;
    if (isSaved !== wasSaved) {
      data.document.broadcastStateless(isSaved ? SAVE_STATUS.saved : SAVE_STATUS.unsaved);
    }
  }

  // An editor asks once it has exchanged its own changes with the server: nothing tells it otherwise
  // whether the changes it made before a lost connection were stored.
  async onStateless({ connection, document, payload }: onStatelessPayload) {
    if (payload === SAVE_STATUS.request) {
      const state = this.saveStates.get(document)!;
      connection.sendStateless(state.changes === state.storedChanges ? SAVE_STATUS.saved : SAVE_STATUS.unsaved);
    }
  }

  /**
   * Stores the latest change of every loaded document, for the shutdown. The documents are first
   * closed to the changes of their editors: a change an editor can no longer send stays in that
   * editor, which shows it as unsaved. Throws when a document is still not stored after a time in
   * which a working API would have taken it several times over.
   */
  async storeLoadedDocuments(instance: Hocuspocus): Promise<void> {
    const documents = Array.from(instance.documents.values());
    for (const document of documents) {
      for (const connection of document.getConnections()) {
        connection.readOnly = true;
      }
    }
    await this.storeDocumentsBefore(Date.now() + 30000, instance, documents);
  }

  // A store that runs is waited for. A store that failed, or that another store kept from running, is
  // started again.
  private async storeDocumentsBefore(deadline: number, instance: Hocuspocus, documents: Document[]): Promise<void> {
    await Promise.all(documents.map((document) => this.storeChanges(instance, document)));
    const unstoredDocuments = documents.filter((document) => !this.isStored(document));
    if (unstoredDocuments.length === 0) {
      return;
    }
    if (Date.now() >= deadline) {
      throw new AppError(`Documents not stored: ${unstoredDocuments.map((document) => document.name).join(", ")}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
    await this.storeDocumentsBefore(deadline, instance, unstoredDocuments);
  }

  // Whether the database has the latest change of the document and no store of an earlier change can
  // still land. A document that is still loading has no state yet, and no change.
  private isStored(document: Document): boolean {
    const state = this.saveStates.get(document);
    return !state || (state.runningStores === 0 && state.changes === state.storedChanges);
  }

  private async storeChanges(instance: Hocuspocus, document: Document): Promise<void> {
    const state = this.saveStates.get(document);
    if (this.isStored(document) || !state || state.runningStores > 0) {
      return;
    }
    try {
      // the payload Hocuspocus builds for a store of its own
      await instance.storeDocumentHooks(
        document,
        {
          instance,
          document,
          documentName: document.name,
          context: state.context,
          clientsCount: document.getConnectionsCount(),
          requestHeaders: {},
          requestParameters: new URLSearchParams(),
          socketId: "server",
        },
        true
      );
    } catch {
      // logged where it failed; storeLoadedDocuments tries again
    }
  }
}
