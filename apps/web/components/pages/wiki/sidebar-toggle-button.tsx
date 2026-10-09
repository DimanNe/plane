/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { LeftSidePaneOutline } from "@makeplane/propel/icons";
import { useLocalStorage } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";

export const useWikiSidebarCollapsed = () => {
  const { storedValue, setValue } = useLocalStorage("wikiSidebarCollapsed", false);
  const isCollapsed = !!storedValue;

  return { isCollapsed, toggleCollapsed: () => setValue(!isCollapsed) };
};

export function WikiSidebarToggleButton() {
  // plane hooks
  const { t } = useTranslation();
  // local storage
  const { isCollapsed, toggleCollapsed } = useWikiSidebarCollapsed();

  return (
    <IconButton
      size="sm"
      variant="ghost"
      icon={<Icon icon={LeftSidePaneOutline} />}
      aria-label={t(
        isCollapsed ? "aria_labels.projects_sidebar.expand_sidebar" : "aria_labels.projects_sidebar.collapse_sidebar"
      )}
      onClick={toggleCollapsed}
    />
  );
}
