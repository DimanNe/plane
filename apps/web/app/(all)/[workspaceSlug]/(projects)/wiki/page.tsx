/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
// components
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { PageHead } from "@/components/core/page-title";
import { UserGreetingsView } from "@/components/home/user-greetings";
import { WikiHeader } from "@/components/pages/wiki/header";
import { WikiRecents } from "@/components/pages/wiki/recents";
import { StickiesWidget } from "@/components/stickies/widget";
// hooks
import { useUser } from "@/hooks/store/user";
// local imports
import type { Route } from "./+types/page";

function WikiHomePage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { data: currentUser } = useUser();

  return (
    <>
      <PageHead title={t("wiki.title")} />
      <AppHeader header={<WikiHeader />} />
      <ContentWrapper className="px-page-x">
        <div className="mx-auto w-full max-w-[800px]">
          {currentUser && <UserGreetingsView user={currentUser} />}
          <div className="py-4">
            <WikiRecents workspaceSlug={workspaceSlug} />
          </div>
          <div className="py-4">
            <StickiesWidget />
          </div>
        </div>
      </ContentWrapper>
    </>
  );
}

export default observer(WikiHomePage);
