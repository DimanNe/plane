/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Outlet } from "react-router";
import useSWR from "swr";
// plane imports
import { EUserPermissions, EUserPermissionsLevel, SIDEBAR_WIDTH } from "@plane/constants";
import { EmptyStateDetailed } from "@plane/blocks/empty-state";
import { useLocalStorage } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { LogoSpinner } from "@/components/common/logo-spinner";
import { MovePageProvider } from "@/components/pages/wiki/move-page-provider";
import { WikiSidebar } from "@/components/pages/wiki/sidebar";
import { useWikiSidebarCollapsed } from "@/components/pages/wiki/sidebar-toggle-button";
import { ResizableSidebar } from "@/components/sidebar/resizable-sidebar";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import type { Route } from "./+types/layout";

function WikiLayout({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { currentWorkspace } = useWorkspace();
  const { allowPermissions } = useUserPermissions();
  const { fetchPagesList, fetchCollections } = usePageStore(EPageStoreType.WORKSPACE);
  // local storage
  const { storedValue: storedSidebarWidth, setValue: setStoredSidebarWidth } = useLocalStorage(
    "wikiSidebarWidth",
    SIDEBAR_WIDTH
  );
  const { isCollapsed: isSidebarCollapsed, toggleCollapsed: toggleSidebarCollapsed } = useWikiSidebarCollapsed();
  // states
  const [sidebarWidth, setSidebarWidth] = useState<number>(storedSidebarWidth ?? SIDEBAR_WIDTH);
  // derived values
  const canAccessWiki = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );
  const isWikiEnabled = !!currentWorkspace?.is_wiki_enabled;
  // fetching the pages and the collections of the wiki
  const { isLoading } = useSWR(canAccessWiki && isWikiEnabled ? `WIKI_PAGES_${workspaceSlug}` : null, () =>
    Promise.all([fetchCollections(workspaceSlug), fetchPagesList(workspaceSlug)])
  );

  if (!canAccessWiki) return <NotAuthorizedView />;

  if (!isWikiEnabled)
    return (
      <EmptyStateDetailed
        assetKey="page"
        title={t("wiki.disabled.title")}
        description={t("wiki.disabled.description")}
      />
    );

  return (
    <MovePageProvider>
      <div className="relative flex size-full overflow-hidden">
        <ResizableSidebar
          width={sidebarWidth}
          setWidth={setSidebarWidth}
          onWidthChange={setStoredSidebarWidth}
          isCollapsed={isSidebarCollapsed}
          toggleCollapsed={toggleSidebarCollapsed}
          togglePeek={() => {}}
        >
          <WikiSidebar />
        </ResizableSidebar>
        <div className="relative flex h-full w-full flex-col overflow-hidden">
          {isLoading ? (
            <div className="grid size-full place-items-center">
              <LogoSpinner />
            </div>
          ) : (
            <Outlet />
          )}
        </div>
      </div>
    </MovePageProvider>
  );
}

export default observer(WikiLayout);
