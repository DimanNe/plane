/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { keyBy, set, sortBy, unset } from "lodash-es";
import { action, computed, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// types
import type { InstructionType, TPage, TPageCollection, TWorkspacePagesResponse } from "@plane/types";
// services
import { PageCollectionService, WorkspacePageService } from "@/services/page";
// store
import type { CoreRootStore } from "../root.store";
import type { TWikiPage } from "./wiki-page";
import { WikiPage } from "./wiki-page";

export type TPageMoveDestination = Partial<Pick<TPage, "parent_id" | "collection_id" | "access" | "sort_order">>;

// the sort order of an item placed between two neighbours of its list
const getSortOrderBetween = (prevSortOrder: number | undefined, nextSortOrder: number | undefined) => {
  if (prevSortOrder !== undefined && nextSortOrder !== undefined) return (prevSortOrder + nextSortOrder) / 2;
  if (nextSortOrder !== undefined) return nextSortOrder / 2;
  return (prevSortOrder ?? 0) + 10000;
};

export interface IWikiPageStore {
  // observables
  data: Record<string, TWikiPage>; // pageId => Page
  collections: Record<string, TPageCollection>; // collectionId => Collection
  // computed
  sortedPages: TWikiPage[];
  collectionIds: string[];
  favoritePageIds: string[];
  archivedPageIds: string[];
  // helper actions
  getPageById: (pageId: string) => TWikiPage | undefined;
  getCollectionById: (collectionId: string) => TPageCollection | undefined;
  getCollectionPageIds: (collectionId: string | null) => string[];
  getRootPageIds: (pageIds: string[]) => string[];
  getTopLevelPageIds: (collectionId: string | null) => string[];
  getChildPageIds: (pageId: string) => string[];
  getNestedPageIds: (pageId: string) => string[];
  getAncestorPageIds: (pageId: string) => string[];
  getDropDestination: (pageId: string, targetPageId: string, instruction: InstructionType) => TPageMoveDestination;
  addPages: (pages: TPage[]) => void;
  updateNestedPages: (pageId: string, data: Partial<TPage>) => void;
  // actions
  fetchPagesList: (workspaceSlug: string) => Promise<TPage[]>;
  fetchPageDetails: (workspaceSlug: string, pageId: string) => Promise<TPage>;
  createPage: (pageData: Partial<TPage>) => Promise<TPage | undefined>;
  removePage: (params: { pageId: string; shouldSync?: boolean }) => Promise<void>;
  movePage: (pageId: string, destination: TPageMoveDestination) => Promise<void>;
  fetchCollections: (workspaceSlug: string) => Promise<TPageCollection[]>;
  createCollection: (data: Partial<TPageCollection>) => Promise<TPageCollection | undefined>;
  updateCollection: (collectionId: string, data: Partial<TPageCollection>) => Promise<void>;
  removeCollection: (collectionId: string) => Promise<void>;
  reorderCollection: (collectionId: string, targetCollectionId: string, instruction: InstructionType) => Promise<void>;
}

export class WikiPageStore implements IWikiPageStore {
  // observables
  data: Record<string, TWikiPage> = {}; // pageId => Page
  collections: Record<string, TPageCollection> = {}; // collectionId => Collection
  // services
  service: WorkspacePageService;
  collectionService: PageCollectionService;
  rootStore: CoreRootStore;

  constructor(private store: CoreRootStore) {
    makeObservable(this, {
      // observables
      data: observable,
      collections: observable,
      // computed
      sortedPages: computed,
      collectionIds: computed,
      favoritePageIds: computed,
      archivedPageIds: computed,
      // helper actions
      addPages: action,
      updateNestedPages: action,
      // actions
      fetchPagesList: action,
      fetchPageDetails: action,
      createPage: action,
      removePage: action,
      movePage: action,
      fetchCollections: action,
      createCollection: action,
      updateCollection: action,
      removeCollection: action,
      reorderCollection: action,
    });
    this.rootStore = store;
    // services
    this.service = new WorkspacePageService();
    this.collectionService = new PageCollectionService();
  }

  get sortedPages() {
    return sortBy(Object.values(this.data), [(page) => page.sort_order]);
  }

  get collectionIds() {
    return sortBy(Object.values(this.collections), [(collection) => collection.sort_order]).map(
      (collection) => collection.id
    );
  }

  get favoritePageIds() {
    return this.sortedPages.filter((page) => page.is_favorite && !page.archived_at).map((page) => page.id) as string[];
  }

  get archivedPageIds() {
    return this.sortedPages.filter((page) => page.archived_at).map((page) => page.id) as string[];
  }

  getPageById = computedFn((pageId: string) => this.data?.[pageId] || undefined);

  getCollectionById = computedFn((collectionId: string) => this.collections?.[collectionId] || undefined);

  // the unarchived pages of a collection at any depth, or the private pages outside collections
  getCollectionPageIds = computedFn(
    (collectionId: string | null) =>
      this.sortedPages
        .filter((page) => (page.collection_id ?? null) === collectionId && !page.archived_at)
        .map((page) => page.id) as string[]
  );

  // the pages whose parent is not among the given pages
  getRootPageIds = (pageIds: string[]) => {
    const pageIdsSet = new Set(pageIds);
    return pageIds.filter((pageId) => !pageIdsSet.has(this.data[pageId]?.parent_id ?? ""));
  };

  // the top level pages of a collection, or the top level private pages outside collections
  getTopLevelPageIds = computedFn((collectionId: string | null) =>
    this.getRootPageIds(this.getCollectionPageIds(collectionId))
  );

  // the pages nested directly under a page; an archived one shows under an archived page only
  getChildPageIds = computedFn((pageId: string) => {
    const isArchived = !!this.data[pageId]?.archived_at;
    return this.sortedPages
      .filter((page) => page.parent_id === pageId && !!page.archived_at === isArchived)
      .map((page) => page.id) as string[];
  });

  // the pages nested under a page at any depth
  getNestedPageIds = computedFn((pageId: string): string[] => {
    const nestedPageIds: string[] = [];
    Object.values(this.data).forEach((page) => {
      if (page.id && page.parent_id === pageId) nestedPageIds.push(page.id, ...this.getNestedPageIds(page.id));
    });
    return nestedPageIds;
  });

  // the pages a page is nested under, the top level one first
  getAncestorPageIds = computedFn((pageId: string): string[] => {
    const parentId = this.data[pageId]?.parent_id;
    if (!parentId || !this.data[parentId]) return [];
    return [...this.getAncestorPageIds(parentId), parentId];
  });

  // where a page goes when it is dropped on another page of a tree
  getDropDestination = (pageId: string, targetPageId: string, instruction: InstructionType): TPageMoveDestination => {
    const targetPage = this.data[targetPageId];
    if (!targetPage || instruction === "make-child") return { parent_id: targetPageId };

    const siblingPageIds = (
      targetPage.parent_id
        ? this.getChildPageIds(targetPage.parent_id)
        : this.getTopLevelPageIds(targetPage.collection_id ?? null)
    ).filter((siblingPageId) => siblingPageId !== pageId);
    const targetIndex = siblingPageIds.indexOf(targetPageId);
    const [prevPageId, nextPageId] =
      instruction === "reorder-above"
        ? [siblingPageIds[targetIndex - 1], targetPageId]
        : [targetPageId, siblingPageIds[targetIndex + 1]];
    const sortOrder = getSortOrderBetween(this.data[prevPageId]?.sort_order, this.data[nextPageId]?.sort_order);

    // a nested page takes the collection and the access of its parent
    if (targetPage.parent_id) return { parent_id: targetPage.parent_id, sort_order: sortOrder };
    return {
      parent_id: null,
      collection_id: targetPage.collection_id ?? null,
      access: targetPage.access,
      sort_order: sortOrder,
    };
  };

  // adds the pages to the store, or updates the ones it already has
  addPages = (pages: TPage[]) => {
    for (const page of pages) {
      if (page?.id) {
        const existingPage = this.getPageById(page.id);
        if (existingPage) {
          // the editor of an open page syncs its title; elsewhere the name is the one the server has
          const shouldUpdateName = !existingPage.editor.editorRef;
          if (shouldUpdateName && page.name !== undefined) existingPage.oldName = page.name;
          existingPage.mutateProperties(page, shouldUpdateName);
        } else {
          set(this.data, [page.id], new WikiPage(this.store, page));
        }
      }
    }
  };

  // applies to the pages nested under a page a change of the page that they follow
  updateNestedPages = (pageId: string, data: Partial<TPage>) => {
    this.getNestedPageIds(pageId).forEach((nestedPageId) => {
      this.data[nestedPageId]?.mutateProperties(data);
      // an archived page is no one's favorite
      if (data.archived_at && this.rootStore.favorite.entityMap[nestedPageId])
        this.rootStore.favorite.removeFavoriteFromStore(nestedPageId);
    });
  };

  fetchPagesList = async (workspaceSlug: string) => {
    const knownPageIds = Object.keys(this.data);
    const pages: TPage[] = [];
    let cursor: string | undefined = undefined;
    do {
      // each request needs the cursor of the one before it
      // oxlint-disable-next-line no-await-in-loop
      const response: TWorkspacePagesResponse = await this.service.fetchAll(workspaceSlug, cursor);
      pages.push(...response.results);
      cursor = response.next_page_results ? response.next_cursor : undefined;
    } while (cursor);

    runInAction(() => {
      // the pages deleted since the last fetch; a page created while this fetch ran is not among the known ones
      const fetchedPageIds = new Set(pages.map((page) => page.id));
      knownPageIds.filter((pageId) => !fetchedPageIds.has(pageId)).forEach((pageId) => unset(this.data, [pageId]));
      this.addPages(pages);
    });

    return pages;
  };

  // opening a page counts as a visit
  fetchPageDetails = async (workspaceSlug: string, pageId: string) => {
    const page = await this.service.fetchById(workspaceSlug, pageId);
    runInAction(() => {
      this.addPages([page]);
    });

    return page;
  };

  createPage = async (pageData: Partial<TPage>) => {
    const { workspaceSlug } = this.store.router;
    if (!workspaceSlug) return undefined;

    const page = await this.service.create(workspaceSlug, pageData);
    await this.fetchCollectionOfPage(workspaceSlug, page);
    runInAction(() => {
      this.addPages([page]);
    });

    return page;
  };

  // the pages nested under a deleted page are deleted with it
  removePage = async ({ pageId, shouldSync = true }: { pageId: string; shouldSync?: boolean }) => {
    const { workspaceSlug } = this.store.router;
    if (!workspaceSlug || !pageId) return undefined;

    if (shouldSync) await this.service.remove(workspaceSlug, pageId);
    runInAction(() => {
      [pageId, ...this.getNestedPageIds(pageId)].forEach((removedPageId) => {
        unset(this.data, [removedPageId]);
        if (this.rootStore.favorite.entityMap[removedPageId])
          this.rootStore.favorite.removeFavoriteFromStore(removedPageId);
      });
    });
  };

  // moves a page under another page, into a collection or out of it, or to another position; its nested pages
  // follow its collection and access
  movePage = async (pageId: string, destination: TPageMoveDestination) => {
    const { workspaceSlug } = this.store.router;
    if (!workspaceSlug) return undefined;

    const page = await this.service.update(workspaceSlug, pageId, destination);
    await this.fetchCollectionOfPage(workspaceSlug, page);
    runInAction(() => {
      const { parent_id, collection_id, access, sort_order } = page;
      this.getPageById(pageId)?.mutateProperties({ parent_id, collection_id, access, sort_order });
      this.updateNestedPages(pageId, { collection_id, access });
    });
  };

  // the first public page of a workspace creates the default collection
  private fetchCollectionOfPage = async (workspaceSlug: string, page: TPage) => {
    if (page.collection_id && !this.collections[page.collection_id]) await this.fetchCollections(workspaceSlug);
  };

  fetchCollections = async (workspaceSlug: string) => {
    const collections = await this.collectionService.fetchAll(workspaceSlug);
    runInAction(() => {
      this.collections = keyBy(collections, "id");
    });

    return collections;
  };

  createCollection = async (data: Partial<TPageCollection>) => {
    const { workspaceSlug } = this.store.router;
    if (!workspaceSlug) return undefined;

    const collection = await this.collectionService.create(workspaceSlug, data);
    runInAction(() => {
      set(this.collections, [collection.id], collection);
    });

    return collection;
  };

  updateCollection = async (collectionId: string, data: Partial<TPageCollection>) => {
    const { workspaceSlug } = this.store.router;
    if (!workspaceSlug) return undefined;

    const collection = await this.collectionService.update(workspaceSlug, collectionId, data);
    runInAction(() => {
      set(this.collections, [collection.id], collection);
    });
  };

  // the API moves or archives the pages of a deleted collection
  removeCollection = async (collectionId: string) => {
    const { workspaceSlug } = this.store.router;
    if (!workspaceSlug) return undefined;

    await this.collectionService.remove(workspaceSlug, collectionId);
    await Promise.all([this.fetchCollections(workspaceSlug), this.fetchPagesList(workspaceSlug)]);
  };

  // moves a collection above or below another collection of the wiki sidebar
  reorderCollection = async (collectionId: string, targetCollectionId: string, instruction: InstructionType) => {
    const siblingCollectionIds = this.collectionIds.filter(
      (siblingCollectionId) => siblingCollectionId !== collectionId
    );
    const targetIndex = siblingCollectionIds.indexOf(targetCollectionId);
    const [prevCollectionId, nextCollectionId] =
      instruction === "reorder-above"
        ? [siblingCollectionIds[targetIndex - 1], targetCollectionId]
        : [targetCollectionId, siblingCollectionIds[targetIndex + 1]];

    await this.updateCollection(collectionId, {
      sort_order: getSortOrderBetween(
        this.collections[prevCollectionId]?.sort_order,
        this.collections[nextCollectionId]?.sort_order
      ),
    });
  };
}
