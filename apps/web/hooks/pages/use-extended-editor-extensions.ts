/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createElement, useMemo } from "react";
// plane imports
import { setToast } from "@plane/blocks/toast";
import type { IEditorPropsExtended, TNestedPageBlockConfig } from "@plane/editor";
import { useTranslation } from "@plane/i18n";
import type { TSearchEntityRequestPayload, TSearchResponse } from "@plane/types";
// components
import { LinkPagesBlock } from "@/components/pages/editor/link-pages-block";
import { NestedPageBlock } from "@/components/pages/editor/nested-page-block";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
// store
import type { TPageInstance } from "@/store/pages/base-page";

export type TExtendedEditorExtensionsHookParams = {
  workspaceSlug: string;
  page: TPageInstance;
  storeType: EPageStoreType;
  fetchEntity: (payload: TSearchEntityRequestPayload) => Promise<TSearchResponse>;
  getRedirectionLink: (pageId?: string) => string;
  extensionHandlers?: Map<string, unknown>;
  projectId?: string;
};

export type TExtendedEditorExtensionsConfig = IEditorPropsExtended;

// The page blocks. An editor that only shows a document creates no pages. A Link pages block lists pages of the wiki.
export const getPageBlocksEditorProps = (
  storeType: EPageStoreType,
  createPage?: TNestedPageBlockConfig["createPage"]
): TExtendedEditorExtensionsConfig => ({
  nestedPage: {
    createPage,
    widgetCallback: (props) => createElement(NestedPageBlock, { ...props, storeType }),
  },
  ...(storeType === EPageStoreType.WORKSPACE && {
    linkPages: {
      widgetCallback: (props) => createElement(LinkPagesBlock, props),
    },
  }),
});

export const useExtendedEditorProps = (
  params: TExtendedEditorExtensionsHookParams
): TExtendedEditorExtensionsConfig => {
  const { page, storeType } = params;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { createPage } = usePageStore(storeType);
  // derived values
  const pageId = page.id;
  const errorTitle = t("toast.error");
  const errorMessage = t("wiki_collections.toasts.create_page_error");

  return useMemo(
    () =>
      getPageBlocksEditorProps(storeType, async () => {
        try {
          const nestedPage = await createPage({ parent_id: pageId });
          return nestedPage?.id;
        } catch {
          setToast({ type: "error", title: errorTitle, message: errorMessage });
          return undefined;
        }
      }),
    [createPage, errorMessage, errorTitle, pageId, storeType]
  );
};
