/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { FolderOutline } from "@makeplane/propel/icons";
import { Breadcrumbs } from "@plane/blocks/breadcrumb";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { SwitcherIcon } from "@/components/common/switcher-label";
import { WikiHeader } from "@/components/pages/wiki/header";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { useAppRouter } from "@/hooks/use-app-router";

type Props = {
  collectionId: string;
};

export const WikiCollectionHeader = observer(function WikiCollectionHeader(props: Props) {
  const { collectionId } = props;
  // states
  const [isCreatingPage, setIsCreatingPage] = useState(false);
  // router
  const router = useAppRouter();
  const { workspaceSlug } = useParams();
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getCollectionById, createPage } = usePageStore(EPageStoreType.WORKSPACE);
  // derived values
  const collection = getCollectionById(collectionId);

  const handleCreatePage = async () => {
    setIsCreatingPage(true);
    try {
      const page = await createPage({ collection_id: collectionId });
      if (page?.id) router.push(`/${workspaceSlug}/wiki/pages/${page.id}`);
    } catch {
      setToast({
        type: "error",
        title: t("toast.error"),
        message: t("wiki_collections.toasts.create_page_in_collection_error"),
      });
    } finally {
      setIsCreatingPage(false);
    }
  };

  if (!collection) return <WikiHeader />;

  return (
    <WikiHeader
      breadcrumbs={[
        <Breadcrumbs.Item
          key={collectionId}
          component={
            <BreadcrumbLink
              label={collection.name}
              icon={<SwitcherIcon logo_props={collection.logo_props} LabelIcon={FolderOutline} size={16} />}
            />
          }
        />,
      ]}
    >
      <Button
        variant="primary"
        size="md"
        stretch="auto"
        label={t("wiki_collections.header.add_page")}
        onClick={() => void handleCreatePage()}
        loading={isCreatingPage}
      />
    </WikiHeader>
  );
});
