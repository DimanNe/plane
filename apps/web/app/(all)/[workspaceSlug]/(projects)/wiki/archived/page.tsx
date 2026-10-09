/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { ArchiveOutline } from "@makeplane/propel/icons";
import { Breadcrumbs } from "@plane/blocks/breadcrumb";
import { useTranslation } from "@plane/i18n";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { PageHead } from "@/components/core/page-title";
import { WikiHeader } from "@/components/pages/wiki/header";
import { WikiPagesList } from "@/components/pages/wiki/pages-list";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

function WikiArchivedPage() {
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { archivedPageIds } = usePageStore(EPageStoreType.WORKSPACE);
  // derived values
  const title = t("wiki_collections.predefined.archived");

  return (
    <>
      <PageHead title={title} />
      <AppHeader
        header={
          <WikiHeader
            breadcrumbs={[
              <Breadcrumbs.Item
                key="archived"
                component={<BreadcrumbLink label={title} icon={<ArchiveOutline className="h-4 w-4 text-tertiary" />} />}
              />,
            ]}
          />
        }
      />
      <ContentWrapper>
        <WikiPagesList
          title={<h3 className="truncate text-16 font-medium">{title}</h3>}
          pageIds={archivedPageIds}
          emptyStateTitle={t("project_empty_state.archive_pages.title")}
          emptyStateDescription={t("project_empty_state.archive_pages.description")}
        />
      </ContentWrapper>
    </>
  );
}

export default observer(WikiArchivedPage);
