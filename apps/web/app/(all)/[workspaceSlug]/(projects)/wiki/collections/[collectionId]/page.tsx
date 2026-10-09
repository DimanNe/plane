/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EPageAccess } from "@plane/constants";
import { Badge } from "@makeplane/propel/components/badge";
import { GlobeOutline, LockOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
// components
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { PageHead } from "@/components/core/page-title";
import { WikiNotFound } from "@/components/pages/wiki/not-found";
import { WikiPagesList } from "@/components/pages/wiki/pages-list";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
// local imports
import type { Route } from "./+types/page";
import { WikiCollectionHeader } from "./header";

function WikiCollectionPage({ params }: Route.ComponentProps) {
  const { collectionId } = params;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getCollectionById, getCollectionPageIds } = usePageStore(EPageStoreType.WORKSPACE);
  // derived values
  const collection = getCollectionById(collectionId);
  const isPrivate = collection?.access === EPageAccess.PRIVATE;

  return (
    <>
      <PageHead title={collection?.name} />
      <AppHeader header={<WikiCollectionHeader collectionId={collectionId} />} />
      <ContentWrapper>
        {collection ? (
          <WikiPagesList
            key={collectionId}
            title={
              <div className="flex items-center gap-2">
                <h3 className="truncate text-16 font-medium">{collection.name}</h3>
                <Badge
                  variant="neutral"
                  size="sm"
                  startIcon={isPrivate ? <LockOutline className="size-3" /> : <GlobeOutline className="size-3" />}
                  label={t(isPrivate ? "common.access.private" : "common.access.public")}
                />
              </div>
            }
            pageIds={getCollectionPageIds(collectionId)}
            emptyStateTitle={t("wiki_collections.list.no_pages_title")}
            emptyStateDescription={t("wiki_collections.list.no_pages_description")}
          />
        ) : (
          <WikiNotFound />
        )}
      </ContentWrapper>
    </>
  );
}

export default observer(WikiCollectionPage);
