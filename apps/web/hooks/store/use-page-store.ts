/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext } from "react";
// context
import { StoreContext } from "@/lib/store-context";
// mobx store
import type { IProjectPageStore } from "@/store/pages/project-page.store";
import type { IWikiPageStore } from "@/store/pages/wiki-page.store";

export enum EPageStoreType {
  PROJECT = "PROJECT_PAGE",
  WORKSPACE = "WORKSPACE_PAGE",
}

export type TReturnType = {
  [EPageStoreType.PROJECT]: IProjectPageStore;
  [EPageStoreType.WORKSPACE]: IWikiPageStore;
};

export const usePageStore = <T extends EPageStoreType>(storeType: T): TReturnType[T] => {
  const context = useContext(StoreContext);
  if (context === undefined) throw new Error("usePageStore must be used within StoreProvider");

  const pageStores: TReturnType = {
    [EPageStoreType.PROJECT]: context.projectPages,
    [EPageStoreType.WORKSPACE]: context.wikiPages,
  };

  return pageStores[storeType];
};
