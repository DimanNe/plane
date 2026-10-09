/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { Switch } from "@makeplane/propel/components/switch";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
// components
import { PageHead } from "@/components/core/page-title";
import { SettingsBoxedControlItem } from "@/components/settings/boxed-control-item";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
// local imports
import type { Route } from "./+types/page";
import { WikiWorkspaceSettingsHeader } from "./header";

function WikiSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  // store hooks
  const { currentWorkspace, updateWorkspace } = useWorkspace();
  // translation
  const { t } = useTranslation();
  // derived values
  const pageTitle = currentWorkspace?.name
    ? `${currentWorkspace.name} - ${t("workspace_settings.settings.wiki.title")}`
    : undefined;
  const isWikiEnabled = !!currentWorkspace?.is_wiki_enabled;

  const handleToggle = () => {
    updateWorkspace(workspaceSlug, { is_wiki_enabled: !isWikiEnabled }).catch(() =>
      setToast({
        type: "error",
        title: t("toast.error"),
        message: t("workspace_settings.settings.wiki.toggle_error"),
      })
    );
  };

  return (
    <SettingsContentWrapper header={<WikiWorkspaceSettingsHeader />}>
      <PageHead title={pageTitle} />
      <section className="w-full">
        <SettingsHeading
          title={t("workspace_settings.settings.wiki.heading")}
          description={t("workspace_settings.settings.wiki.description")}
        />
        <div className="mt-7">
          <SettingsBoxedControlItem
            title={t("workspace_settings.settings.wiki.toggle_title")}
            description={t("workspace_settings.settings.wiki.toggle_description")}
            control={
              <Switch
                size="sm"
                checked={isWikiEnabled}
                onCheckedChange={handleToggle}
                aria-label={t("workspace_settings.settings.wiki.toggle_title")}
              />
            }
          />
        </div>
      </section>
    </SettingsContentWrapper>
  );
}

export default observer(WikiSettingsPage);
