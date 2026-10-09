/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useParams } from "next/navigation";
// plane imports
import { BookClosedOutline } from "@makeplane/propel/icons";
import { Breadcrumbs } from "@plane/blocks/breadcrumb";
import { Header } from "@plane/blocks/layout";
import { useTranslation } from "@plane/i18n";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
// local imports
import { useWikiSidebarCollapsed, WikiSidebarToggleButton } from "./sidebar-toggle-button";

type Props = {
  // the `Breadcrumbs.Item`s that follow the wiki one
  breadcrumbs?: React.ReactElement[];
  children?: React.ReactNode;
};

export function WikiHeader(props: Props) {
  const { breadcrumbs = [], children } = props;
  // params
  const { workspaceSlug } = useParams();
  // plane hooks
  const { t } = useTranslation();
  // local storage
  const { isCollapsed } = useWikiSidebarCollapsed();

  return (
    <Header>
      <Header.LeftItem>
        <div className="flex items-center gap-2">
          {isCollapsed && <WikiSidebarToggleButton />}
          <Breadcrumbs>
            {[
              <Breadcrumbs.Item
                key="wiki"
                component={
                  <BreadcrumbLink
                    label={t("wiki.title")}
                    href={breadcrumbs.length > 0 ? `/${workspaceSlug}/wiki` : undefined}
                    icon={<BookClosedOutline className="h-4 w-4 text-tertiary" />}
                  />
                }
              />,
              ...breadcrumbs,
            ]}
          </Breadcrumbs>
        </div>
      </Header.LeftItem>
      {children && <Header.RightItem>{children}</Header.RightItem>}
    </Header>
  );
}
