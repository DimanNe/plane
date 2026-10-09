/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
// components
import { RecentsEmptyState } from "@/components/home/widgets/empty-states";
import { EWidgetKeys, WidgetLoader } from "@/components/home/widgets/loaders";
import { PageListBlock } from "@/components/pages/list/block";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
// services
import { WorkspaceService } from "@/services/workspace.service";
const workspaceService = new WorkspaceService();

const storeType = EPageStoreType.WORKSPACE;

type Props = {
  workspaceSlug: string;
};

export const WikiRecents = observer(function WikiRecents(props: Props) {
  const { workspaceSlug } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getPageById } = usePageStore(storeType);
  // the recently visited pages of the workspace; the ones of projects are not in the wiki store
  const { data: recents, isLoading } = useSWR(`WIKI_RECENT_PAGES_${workspaceSlug}`, () =>
    workspaceService.fetchWorkspaceRecents(workspaceSlug, "page")
  );
  // derived values
  const pageIds = (recents ?? [])
    .map((recent) => recent.entity_identifier)
    .filter((pageId) => !!getPageById(pageId) && !getPageById(pageId)?.archived_at);

  return (
    <div>
      <div className="mb-2 text-14 font-semibold text-tertiary">{t("home.recents.title")}</div>
      {isLoading && <WidgetLoader widgetKey={EWidgetKeys.RECENT_ACTIVITY} />}
      {!isLoading && pageIds.length === 0 && <RecentsEmptyState type="page" />}
      {!isLoading && pageIds.map((pageId) => <PageListBlock key={pageId} pageId={pageId} storeType={storeType} />)}
    </div>
  );
});
