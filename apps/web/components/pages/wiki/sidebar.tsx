/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
// plane imports
import { EPageAccess } from "@plane/constants";
import { Collapsible } from "@makeplane/propel/components/collapsible";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { ScrollArea } from "@makeplane/propel/components/scroll-area";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { AddOutline, AddPageOutline, ArchiveOutline, HomeOutline } from "@makeplane/propel/icons";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { InstructionType, TPage } from "@plane/types";
// components
import { PageTreeNode } from "@/components/pages/nesting/page-tree";
import { SidebarAddButton } from "@/components/sidebar/add-button";
import { SidebarNavItem } from "@/components/sidebar/sidebar-navigation";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { useAppRouter } from "@/hooks/use-app-router";
// local imports
import { WikiCollectionItem } from "./collection-item";
import { WikiCollectionModal } from "./collection-modal";
import { useMovePage } from "./move-page-provider";
import { WikiSidebarToggleButton } from "./sidebar-toggle-button";

const storeType = EPageStoreType.WORKSPACE;

type TWikiSidebarSectionProps = {
  title: string;
  // the label and the action of the button shown on hover
  addLabel?: string;
  onAdd?: () => void;
  children: React.ReactNode;
};

function WikiSidebarSection(props: TWikiSidebarSectionProps) {
  const { title, addLabel, onAdd, children } = props;

  return (
    <Collapsible
      render={<div className="group/wiki-section" />}
      placement="sidebar"
      defaultOpen
      trigger={<span className="text-13 font-semibold whitespace-nowrap text-placeholder">{title}</span>}
      trailing={
        addLabel &&
        onAdd && (
          <span className="flex items-center opacity-0 group-hover/wiki-section:opacity-100 focus-within:opacity-100">
            <Tooltip label={addLabel}>
              <IconButton
                variant="ghost"
                size="xs"
                icon={<Icon icon={AddOutline} />}
                aria-label={addLabel}
                onClick={onAdd}
              />
            </Tooltip>
          </span>
        )
      }
    >
      <div className="flex flex-col gap-0.5">{children}</div>
    </Collapsible>
  );
}

export const WikiSidebar = observer(function WikiSidebar() {
  // states
  const [isCreateCollectionModalOpen, setIsCreateCollectionModalOpen] = useState(false);
  // router
  const router = useAppRouter();
  const pathname = usePathname();
  const { workspaceSlug } = useParams();
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { collectionIds, favoritePageIds, getTopLevelPageIds, getDropDestination, createPage } =
    usePageStore(storeType);
  const movePage = useMovePage();
  // derived values
  const wikiLink = `/${workspaceSlug}/wiki`;
  const privatePageIds = getTopLevelPageIds(null);

  const handleCreatePage = useCallback(
    async (pageData: Partial<TPage>) => {
      try {
        const page = await createPage(pageData);
        if (page?.id) router.push(`/${workspaceSlug}/wiki/pages/${page.id}`);
      } catch {
        setToast({
          type: "error",
          title: t("toast.error"),
          message: t("wiki_collections.toasts.create_page_error"),
        });
      }
    },
    [createPage, router, t, workspaceSlug]
  );

  const handleCreateNestedPage = useCallback(
    (parentPageId: string) => void handleCreatePage({ parent_id: parentPageId }),
    [handleCreatePage]
  );

  const handlePageDrop = useCallback(
    (pageId: string, targetPageId: string, instruction: InstructionType) =>
      movePage(pageId, getDropDestination(pageId, targetPageId, instruction)),
    [getDropDestination, movePage]
  );

  return (
    <>
      {isCreateCollectionModalOpen && <WikiCollectionModal onClose={() => setIsCreateCollectionModalOpen(false)} />}
      <div className="flex h-full w-full flex-col">
        <div className="flex flex-col gap-3 px-3">
          <div className="flex items-center justify-between gap-2 px-2">
            <span className="pt-1 text-16 font-medium text-primary">{t("wiki.title")}</span>
            <WikiSidebarToggleButton />
          </div>
          <SidebarAddButton
            label={
              <>
                <AddPageOutline className="size-4" />
                <span className="truncate text-13 font-medium">{t("wiki.new_page")}</span>
              </>
            }
            onClick={() => void handleCreatePage({ access: EPageAccess.PUBLIC })}
          />
        </div>
        <ScrollArea orientation="vertical">
          <div className="flex flex-col gap-3 overflow-x-hidden px-3 pt-3 pb-0.5">
            <Link href={wikiLink}>
              <SidebarNavItem isActive={pathname === `${wikiLink}/`}>
                <div className="flex items-center gap-1.5 py-[1px]">
                  <HomeOutline className="size-4 flex-shrink-0" />
                  <p className="text-13 leading-5 font-medium">{t("home.title")}</p>
                </div>
              </SidebarNavItem>
            </Link>
            {favoritePageIds.length > 0 && (
              <WikiSidebarSection title={t("favorites")}>
                {favoritePageIds.map((pageId) => (
                  <PageTreeNode key={pageId} pageId={pageId} storeType={storeType} variant="sidebar" />
                ))}
              </WikiSidebarSection>
            )}
            <WikiSidebarSection
              title={t("wiki_collections.title")}
              addLabel={t("wiki_collections.create_modal.title")}
              onAdd={() => setIsCreateCollectionModalOpen(true)}
            >
              {collectionIds.map((collectionId, index) => (
                <WikiCollectionItem
                  key={collectionId}
                  collectionId={collectionId}
                  isLastChild={index === collectionIds.length - 1}
                  onCreatePage={handleCreatePage}
                  onCreateNestedPage={handleCreateNestedPage}
                  onPageDrop={handlePageDrop}
                />
              ))}
            </WikiSidebarSection>
            <WikiSidebarSection
              title={t("wiki_collections.predefined.private")}
              addLabel={t("wiki_collections.menu.create_new_page")}
              onAdd={() => void handleCreatePage({ access: EPageAccess.PRIVATE })}
            >
              {privatePageIds.map((pageId, index) => (
                <PageTreeNode
                  key={pageId}
                  pageId={pageId}
                  storeType={storeType}
                  variant="sidebar"
                  isLastChild={index === privatePageIds.length - 1}
                  onCreateNestedPage={handleCreateNestedPage}
                  onDrop={handlePageDrop}
                />
              ))}
            </WikiSidebarSection>
            <Link href={`${wikiLink}/archived`}>
              <SidebarNavItem isActive={pathname === `${wikiLink}/archived/`}>
                <div className="flex items-center gap-1.5 py-[1px]">
                  <ArchiveOutline className="size-4 flex-shrink-0" />
                  <p className="text-13 leading-5 font-medium">{t("wiki_collections.predefined.archived")}</p>
                </div>
              </SidebarNavItem>
            </Link>
          </div>
        </ScrollArea>
      </div>
    </>
  );
});
