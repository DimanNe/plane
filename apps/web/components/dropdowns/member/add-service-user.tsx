/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { AddOutline, LoadingOutline } from "@makeplane/propel/icons";
// plane imports
import { useSelectContext } from "@plane/blocks/select";
import { setToast } from "@plane/blocks/toast";
import { EUserPermissionsLevel } from "@plane/constants";
import { useLatestCallback } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";
import { EUserPermissions } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// stores
import { addServiceUserToProject } from "@/store/member/service-user";

type TEntryProps = {
  name: string;
  onAdd: (name: string) => Promise<void>;
};

/** What a member menu shows when the typed text matches nobody: the offer to add a service user of that name.
 *  A click and Enter take it, as in the menu of labels. */
function AddServiceUserEntry({ name, onAdd }: TEntryProps) {
  // states
  const [isAdding, setIsAdding] = useState(false);
  // a second press can come before the first one is drawn
  const isRequested = useRef(false);
  // translation
  const { t } = useTranslation();
  // select context
  const { close } = useSelectContext();

  const handleAdd = useLatestCallback(async () => {
    if (isRequested.current) return;
    isRequested.current = true;
    setIsAdding(true);
    try {
      await onAdd(name);
      close();
    } catch (error) {
      const reason = error as { detail?: string; name?: string[]; error?: string } | undefined;
      const message = reason?.detail ?? reason?.name?.[0] ?? reason?.error ?? t("failed_to_add_service_user");
      setToast({ type: "error", title: t("error"), message });
    } finally {
      isRequested.current = false;
      setIsAdding(false);
    }
  });

  // the focus is in the search field of the menu, which has nothing to pick with Enter while this is shown
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Enter" || event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
      event.preventDefault();
      event.stopPropagation();
      void handleAdd();
    };
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [handleAdd]);

  const EntryIcon = isAdding ? LoadingOutline : AddOutline;

  return (
    <button
      type="button"
      className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-body-xs-regular text-secondary hover:bg-layer-transparent-hover"
      onClick={() => void handleAdd()}
      disabled={isAdding}
    >
      <EntryIcon className={cn("size-3.5 shrink-0", { "animate-spin": isAdding })} />
      <span className="truncate">{t(isAdding ? "adding_service_user" : "add_service_user", { name })}</span>
    </button>
  );
}

type TArgs = {
  /** The project whose members the menu offers; a menu of other members offers no service user. */
  projectId: string | undefined;
  /** Picks the member in the menu, as a click on its option would. */
  onAdded: (userId: string) => void;
};

/**
 * What a menu of a project's members shows when the typed text matches nobody: the offer to add a service user
 * of that name to the project and to pick it. `undefined`, which leaves the menu its own text, for somebody
 * who may not change the assignees of the project's work items.
 */
export const useAddServiceUserEntry = ({ projectId, onAdded }: TArgs): ((query: string) => ReactNode) | undefined => {
  // router params
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString();
  // store hooks
  const memberRoot = useMember();
  const projectStore = useProject();
  const { allowPermissions } = useUserPermissions();
  // translation
  const { t } = useTranslation();

  if (!slug || !projectId) return undefined;
  const roles = [EUserPermissions.ADMIN, EUserPermissions.MEMBER];
  if (!allowPermissions(roles, EUserPermissionsLevel.PROJECT, slug, projectId)) return undefined;

  return (query: string) => {
    const name = query.trim();
    if (!name) return t("no_matching_results");
    return (
      <AddServiceUserEntry
        name={name}
        onAdd={async (typed) =>
          onAdded(await addServiceUserToProject(memberRoot, projectStore, slug, projectId, typed))
        }
      />
    );
  };
};
