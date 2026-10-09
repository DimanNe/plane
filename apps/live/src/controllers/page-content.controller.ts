/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Hocuspocus } from "@hocuspocus/server";
import type { Request, Response } from "express";
import * as Y from "yjs";
import { z } from "zod";
// plane imports
import { Controller, Middleware, Post } from "@plane/decorators";
import {
  getAllDocumentFormatsFromDocumentEditorBinaryData,
  getBinaryDataFromDocumentEditorHTMLString,
} from "@plane/editor";
import { logger } from "@plane/logger";
// lib
import { requireSecretKey } from "@/lib/auth-middleware";

const pageContentSchema = z.object({
  page_id: z.string().uuid(),
  description_binary: z.string(),
  name: z.string().nullish(),
  description_html: z.string().nullish(),
});

/**
 * The name and the description of a page are parts of its collaborative document, and an editor
 * that has the page open stores that document over them. A writer other than an editor (the API
 * serving an agent) therefore sends its change here, and it is made inside the document: the loaded
 * one when the page is open, so that the editors show it, otherwise the stored one the API sends.
 * The API stores the returned document.
 */
@Controller("/page-content")
export class PageContentController {
  [key: string]: unknown;
  private readonly hocusPocusServer: Hocuspocus;

  constructor(hocusPocusServer: Hocuspocus) {
    this.hocusPocusServer = hocusPocusServer;
  }

  @Post("/")
  @Middleware(requireSecretKey)
  async replacePageContent(req: Request, res: Response) {
    const validatedData = pageContentSchema.safeParse(req.body);
    if (!validatedData.success) {
      return res.status(400).json({ message: validatedData.error.message });
    }
    const { page_id, description_binary, name, description_html } = validatedData.data;

    try {
      // a document that is still loading is empty: a change made now would be joined with the stored content
      await this.hocusPocusServer.loadingDocuments.get(page_id);
      const loadedDocument = this.hocusPocusServer.documents.get(page_id);
      const document = loadedDocument ?? new Y.Doc();
      if (!loadedDocument) {
        Y.applyUpdate(document, Buffer.from(description_binary, "base64"));
      }

      const replacement = new Y.Doc();
      Y.applyUpdate(replacement, getBinaryDataFromDocumentEditorHTMLString(description_html ?? "<p></p>", name ?? ""));
      // With a connection as the origin, Hocuspocus stores this change as it stores the change of an editor.
      document.transact(() => {
        const fields = [
          ["default", description_html],
          ["title", name],
        ] as const;
        for (const [field, value] of fields) {
          if (value == null) continue;
          const fragment = document.getXmlFragment(field);
          fragment.delete(0, fragment.length);
          fragment.insert(
            0,
            replacement
              .getXmlFragment(field)
              .toArray()
              .map((node) => node.clone() as Y.XmlElement | Y.XmlText)
          );
        }
      }, loadedDocument?.getConnections()[0]);

      const { contentBinaryEncoded, contentHTML, contentJSON } = getAllDocumentFormatsFromDocumentEditorBinaryData(
        Y.encodeStateAsUpdate(document),
        false
      );
      res.status(200).json({
        description_binary: contentBinaryEncoded,
        description_html: contentHTML,
        description_json: contentJSON,
      });
    } catch (error) {
      logger.error("PAGE_CONTENT_CONTROLLER: Internal server error", error);
      res.status(500).json({ message: "Internal server error." });
    }
  }
}
