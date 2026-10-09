/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { computed, makeObservable } from "mobx";
import { computedFn } from "mobx-utils";
// constants
import { EPageAccess, EUserPermissions } from "@plane/constants";
import type { TPage } from "@plane/types";
// plane web store
import type { RootStore } from "@/store/root.store";
// services
import { WorkspacePageService } from "@/services/page";
const workspacePageService = new WorkspacePageService();
// store
import { BasePage } from "./base-page";
import type { TPageInstance } from "./base-page";

export type TWikiPage = TPageInstance;

export class WikiPage extends BasePage implements TWikiPage {
  constructor(store: RootStore, page: TPage) {
    // required fields for API calls
    const { workspaceSlug } = store.router;
    // initialize base instance
    super(store, page, {
      update: async (payload) => {
        if (!workspaceSlug || !page.id) throw new Error("Missing required fields.");
        return await workspacePageService.update(workspaceSlug, page.id, payload);
      },
      updateDescription: async (document) => {
        if (!workspaceSlug || !page.id) throw new Error("Missing required fields.");
        await workspacePageService.updateDescription(workspaceSlug, page.id, document);
      },
      updateAccess: async (payload) => {
        if (!page.id) throw new Error("Missing required fields.");
        await store.wikiPages.movePage(page.id, payload);
      },
      lock: async (recursive) => {
        if (!workspaceSlug || !page.id) throw new Error("Missing required fields.");
        await workspacePageService.lock(workspaceSlug, page.id, recursive);
        if (recursive) store.wikiPages.updateNestedPages(page.id, { is_locked: true });
      },
      unlock: async (recursive) => {
        if (!workspaceSlug || !page.id) throw new Error("Missing required fields.");
        await workspacePageService.unlock(workspaceSlug, page.id, recursive);
        if (recursive) store.wikiPages.updateNestedPages(page.id, { is_locked: false });
      },
      archive: async () => {
        if (!workspaceSlug || !page.id) throw new Error("Missing required fields.");
        const response = await workspacePageService.archive(workspaceSlug, page.id);
        store.wikiPages.updateNestedPages(page.id, { archived_at: response.archived_at });
        return response;
      },
      restore: async () => {
        if (!workspaceSlug || !page.id) throw new Error("Missing required fields.");
        await workspacePageService.restore(workspaceSlug, page.id);
        store.wikiPages.updateNestedPages(page.id, { archived_at: null });
      },
      duplicate: async () => {
        if (!workspaceSlug || !page.id) throw new Error("Missing required fields.");
        const duplicatedPage = await workspacePageService.duplicate(workspaceSlug, page.id);
        store.wikiPages.addPages([duplicatedPage]);
        return duplicatedPage;
      },
    });
    makeObservable(this, {
      // computed
      canCurrentUserAccessPage: computed,
      canCurrentUserEditPage: computed,
      canCurrentUserDuplicatePage: computed,
      canCurrentUserLockPage: computed,
      canCurrentUserChangeAccess: computed,
      canCurrentUserArchivePage: computed,
      canCurrentUserDeletePage: computed,
      canCurrentUserFavoritePage: computed,
      canCurrentUserMovePage: computed,
      isContentEditable: computed,
    });
  }

  private get isCurrentUserOwnerOrAdmin() {
    const { workspaceSlug } = this.rootStore.router;
    const currentUserWorkspaceRole = this.rootStore.user.permission.getWorkspaceRoleByWorkspaceSlug(
      workspaceSlug?.toString() || ""
    );
    return this.isCurrentUserOwner || currentUserWorkspaceRole === EUserPermissions.ADMIN;
  }

  get canCurrentUserAccessPage() {
    const isPagePublic = this.access === EPageAccess.PUBLIC;
    return isPagePublic || this.isCurrentUserOwner;
  }

  get canCurrentUserEditPage() {
    return this.canCurrentUserAccessPage;
  }

  get canCurrentUserDuplicatePage() {
    return this.canCurrentUserAccessPage;
  }

  get canCurrentUserLockPage() {
    return this.isCurrentUserOwnerOrAdmin;
  }

  get canCurrentUserChangeAccess() {
    // a nested page takes the access of its parent
    return !this.parent_id && this.isCurrentUserOwner;
  }

  get canCurrentUserArchivePage() {
    return this.isCurrentUserOwnerOrAdmin;
  }

  get canCurrentUserDeletePage() {
    return this.isCurrentUserOwnerOrAdmin;
  }

  get canCurrentUserFavoritePage() {
    return this.canCurrentUserAccessPage;
  }

  get canCurrentUserMovePage() {
    return this.isCurrentUserOwnerOrAdmin && !this.archived_at && !this.is_locked;
  }

  get isContentEditable() {
    return !this.archived_at && !this.is_locked && this.canCurrentUserEditPage;
  }

  getRedirectionLink = computedFn(() => {
    const { workspaceSlug } = this.rootStore.router;
    return `/${workspaceSlug}/wiki/pages/${this.id}`;
  });
}
