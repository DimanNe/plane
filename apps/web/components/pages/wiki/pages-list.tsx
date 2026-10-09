/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { EmptyStateDetailed } from "@plane/blocks/empty-state";
import { EHeaderVariant, Header } from "@plane/blocks/layout";
import { useTranslation } from "@plane/i18n";
import { getPageName } from "@plane/utils";
// components
import { ListLayout } from "@/components/core/list";
import { PageSearchInput } from "@/components/pages/list/search-input";
import { PageTreeNode } from "@/components/pages/nesting/page-tree";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

const storeType = EPageStoreType.WORKSPACE;

type Props = {
  title: React.ReactNode;
  // the pages of the list at any depth; a page nested under another page of the list shows under it
  pageIds: string[];
  emptyStateTitle: string;
  emptyStateDescription: string;
};

export const WikiPagesList = observer(function WikiPagesList(props: Props) {
  const { title, pageIds, emptyStateTitle, emptyStateDescription } = props;
  // states
  const [searchQuery, setSearchQuery] = useState("");
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getPageById, getRootPageIds } = usePageStore(storeType);
  // derived values
  const filteredPageIds = pageIds.filter((pageId) =>
    getPageName(getPageById(pageId)?.name).toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden">
      <Header variant={EHeaderVariant.SECONDARY}>
        <Header.LeftItem>{title}</Header.LeftItem>
        <Header.RightItem className="items-center">
          <PageSearchInput searchQuery={searchQuery} updateSearchQuery={setSearchQuery} />
        </Header.RightItem>
      </Header>
      <div className="h-full w-full overflow-hidden">
        {pageIds.length === 0 ? (
          <EmptyStateDetailed assetKey="page" title={emptyStateTitle} description={emptyStateDescription} />
        ) : filteredPageIds.length === 0 ? (
          <EmptyStateDetailed
            assetKey="search"
            title={t("common_empty_state.search.title")}
            description={t("common_empty_state.search.description")}
          />
        ) : (
          <ListLayout>
            {getRootPageIds(filteredPageIds).map((pageId) => (
              <PageTreeNode key={pageId} pageId={pageId} storeType={storeType} variant="list" />
            ))}
          </ListLayout>
        )}
      </div>
    </div>
  );
});
