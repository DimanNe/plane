/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane types
import type { TSearchEntityRequestPayload, TWebhookConnectionQueryParams } from "@plane/types";
import { EFileAssetType } from "@plane/types";
// components
import { LogoSpinner } from "@/components/common/logo-spinner";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { PageHead } from "@/components/core/page-title";
import { IssuePeekOverview } from "@/components/issues/peek-overview";
import type { TPageRootConfig, TPageRootHandlers } from "@/components/pages/editor/page-root";
import { PageRoot } from "@/components/pages/editor/page-root";
import { WikiNotFound } from "@/components/pages/wiki/not-found";
// hooks
import { useEditorConfig } from "@/hooks/editor";
import { useEditorAsset } from "@/hooks/store/use-editor-asset";
import { useWorkspace } from "@/hooks/store/use-workspace";
// plane web hooks
import { EPageStoreType, usePage, usePageStore } from "@/hooks/store";
// services
import { WorkspacePageService } from "@/services/page";
import { WorkspaceService } from "@/services/workspace.service";
import type { Route } from "./+types/page";
import { WikiPageDetailsHeader } from "./header";
const workspaceService = new WorkspaceService();
const workspacePageService = new WorkspacePageService();

const storeType = EPageStoreType.WORKSPACE;

function WikiPageDetailsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, pageId } = params;
  // store hooks
  const { createPage, fetchPageDetails } = usePageStore(storeType);
  const page = usePage({
    pageId,
    storeType,
  });
  const { getWorkspaceBySlug } = useWorkspace();
  const { uploadEditorAsset, duplicateEditorAsset } = useEditorAsset();
  // derived values
  const workspaceId = getWorkspaceBySlug(workspaceSlug)?.id ?? "";
  const { canCurrentUserAccessPage, name, updateDescription } = page ?? {};
  // entity search handler
  const fetchEntityCallback = useCallback(
    async (payload: TSearchEntityRequestPayload) => await workspaceService.searchEntity(workspaceSlug, payload),
    [workspaceSlug]
  );
  // editor config
  const { getEditorFileHandlers } = useEditorConfig();
  // fetch page details
  const { error: pageDetailsError } = useSWR(
    `WIKI_PAGE_DETAILS_${pageId}`,
    () => fetchPageDetails(workspaceSlug, pageId),
    {
      revalidateIfStale: true,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  );
  // page root handlers
  const pageRootHandlers: TPageRootHandlers = useMemo(
    () => ({
      create: createPage,
      fetchAllVersions: async (id) => await workspacePageService.fetchAllVersions(workspaceSlug, id),
      fetchDescriptionBinary: async () => await workspacePageService.fetchDescriptionBinary(workspaceSlug, pageId),
      fetchEntity: fetchEntityCallback,
      fetchVersionDetails: async (id, versionId) =>
        await workspacePageService.fetchVersionById(workspaceSlug, id, versionId),
      // a version is restored through the editor: the API has no endpoint for it
      restoreVersion: async () => {},
      getRedirectionLink: (id) => {
        if (id) {
          return `/${workspaceSlug}/wiki/pages/${id}`;
        } else {
          return `/${workspaceSlug}/wiki`;
        }
      },
      updateDescription: updateDescription ?? (async () => {}),
    }),
    [createPage, fetchEntityCallback, pageId, updateDescription, workspaceSlug]
  );
  // page root config
  const pageRootConfig: TPageRootConfig = useMemo(
    () => ({
      fileHandler: getEditorFileHandlers({
        uploadFile: async (blockId, file) => {
          const { asset_id } = await uploadEditorAsset({
            blockId,
            data: {
              entity_identifier: pageId,
              entity_type: EFileAssetType.PAGE_DESCRIPTION,
            },
            file,
            workspaceSlug,
          });
          return asset_id;
        },
        duplicateFile: async (assetId: string) => {
          const { asset_id } = await duplicateEditorAsset({
            assetId,
            entityId: pageId,
            entityType: EFileAssetType.PAGE_DESCRIPTION,
            workspaceSlug,
          });
          return asset_id;
        },
        workspaceId,
        workspaceSlug,
      }),
    }),
    [getEditorFileHandlers, workspaceId, workspaceSlug, uploadEditorAsset, pageId, duplicateEditorAsset]
  );

  const webhookConnectionParams: TWebhookConnectionQueryParams = useMemo(
    () => ({
      documentType: "workspace_page",
      workspaceSlug,
    }),
    [workspaceSlug]
  );

  return (
    <>
      <PageHead title={name} />
      <AppHeader header={<WikiPageDetailsHeader pageId={pageId} />} />
      <ContentWrapper>
        {!page && !pageDetailsError ? (
          <div className="grid size-full place-items-center">
            <LogoSpinner />
          </div>
        ) : !page || pageDetailsError || !canCurrentUserAccessPage ? (
          <WikiNotFound />
        ) : (
          <div className="flex h-full flex-col justify-between">
            <div className="relative flex h-full w-full flex-shrink-0 flex-col overflow-hidden">
              <PageRoot
                config={pageRootConfig}
                handlers={pageRootHandlers}
                storeType={storeType}
                page={page}
                webhookConnectionParams={webhookConnectionParams}
                workspaceSlug={workspaceSlug}
              />
              <IssuePeekOverview />
            </div>
          </div>
        )}
      </ContentWrapper>
    </>
  );
}

export default observer(WikiPageDetailsPage);
