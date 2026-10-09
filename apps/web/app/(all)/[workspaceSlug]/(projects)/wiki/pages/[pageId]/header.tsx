/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { FolderOutline, PagesOutline } from "@makeplane/propel/icons";
import { Breadcrumbs } from "@plane/blocks/breadcrumb";
import { getPageName } from "@plane/utils";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { SwitcherIcon } from "@/components/common/switcher-label";
import { PageHeaderActions } from "@/components/pages/header/actions";
import { PageSyncingBadge } from "@/components/pages/header/syncing-badge";
import { WikiHeader } from "@/components/pages/wiki/header";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

const storeType = EPageStoreType.WORKSPACE;

type Props = {
  pageId: string;
};

export const WikiPageDetailsHeader = observer(function WikiPageDetailsHeader(props: Props) {
  const { pageId } = props;
  // params
  const { workspaceSlug } = useParams();
  // store hooks
  const { getPageById, getCollectionById, getAncestorPageIds } = usePageStore(storeType);
  // derived values
  const page = getPageById(pageId);
  const collection = page?.collection_id ? getCollectionById(page.collection_id) : undefined;

  return (
    <WikiHeader
      breadcrumbs={[
        ...(collection
          ? [
              <Breadcrumbs.Item
                key={collection.id}
                component={
                  <BreadcrumbLink
                    label={collection.name}
                    href={`/${workspaceSlug}/wiki/collections/${collection.id}`}
                    icon={<SwitcherIcon logo_props={collection.logo_props} LabelIcon={FolderOutline} size={16} />}
                  />
                }
              />,
            ]
          : []),
        ...[...getAncestorPageIds(pageId), pageId].map((crumbPageId) => {
          const crumbPage = getPageById(crumbPageId);
          return (
            <Breadcrumbs.Item
              key={crumbPageId}
              component={
                <BreadcrumbLink
                  label={getPageName(crumbPage?.name)}
                  href={crumbPageId === pageId ? undefined : crumbPage?.getRedirectionLink()}
                  icon={<SwitcherIcon logo_props={crumbPage?.logo_props} LabelIcon={PagesOutline} size={16} />}
                />
              }
            />
          );
        }),
      ]}
    >
      {page && (
        <>
          <PageSyncingBadge syncStatus={page.isSyncingWithServer} />
          <PageHeaderActions page={page} storeType={storeType} />
        </>
      )}
    </WikiHeader>
  );
});
