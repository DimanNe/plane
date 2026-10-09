/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createContext, useCallback, useContext, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { EPageAccess } from "@plane/constants";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
// store
import type { TPageMoveDestination } from "@/store/pages/wiki-page.store";

type TMovePage = (pageId: string, destination: TPageMoveDestination) => void;

type TPageMove = {
  pageId: string;
  destination: TPageMoveDestination;
  access: EPageAccess;
};

const MovePageContext = createContext<TMovePage>(() => {});

/**
 * Moves a wiki page. A move that changes who can see the page asks first.
 */
export const useMovePage = () => useContext(MovePageContext);

type Props = {
  children: React.ReactNode;
};

export const MovePageProvider = observer(function MovePageProvider(props: Props) {
  const { children } = props;
  // states
  const [moveToConfirm, setMoveToConfirm] = useState<TPageMove | undefined>(undefined);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getPageById, getCollectionById, movePage } = usePageStore(EPageStoreType.WORKSPACE);
  // derived values
  const errorTitle = t("page_actions.move_page.toasts.error.title");
  const errorMessage = t("page_actions.move_page.toasts.error.message");

  const handleMove = useCallback(
    async (pageId: string, destination: TPageMoveDestination) => {
      try {
        await movePage(pageId, destination);
      } catch {
        setToast({ type: "error", title: errorTitle, message: errorMessage });
      }
    },
    [errorMessage, errorTitle, movePage]
  );

  const handleMoveRequest: TMovePage = useCallback(
    (pageId, destination) => {
      // a nested page takes the access of its parent, a page in a collection the access of the collection
      const access = destination.parent_id
        ? getPageById(destination.parent_id)?.access
        : destination.collection_id
          ? getCollectionById(destination.collection_id)?.access
          : destination.access;

      if (access !== undefined && access !== getPageById(pageId)?.access)
        setMoveToConfirm({ pageId, destination, access });
      else void handleMove(pageId, destination);
    },
    [getCollectionById, getPageById, handleMove]
  );

  const handleConfirm = async () => {
    if (!moveToConfirm) return;
    setIsSubmitting(true);
    await handleMove(moveToConfirm.pageId, moveToConfirm.destination);
    setIsSubmitting(false);
    setMoveToConfirm(undefined);
  };

  const confirmationKey = moveToConfirm?.access === EPageAccess.PUBLIC ? "make_public" : "make_private";

  return (
    <MovePageContext.Provider value={handleMoveRequest}>
      {children}
      <ConfirmDialog
        isOpen={!!moveToConfirm}
        handleClose={() => setMoveToConfirm(undefined)}
        handleSubmit={handleConfirm}
        isSubmitting={isSubmitting}
        title={t(`page_actions.move_page.confirmation.${confirmationKey}.title`)}
        content={t(`page_actions.move_page.confirmation.${confirmationKey}.description`)}
        primaryButtonText={{
          default: t("page_actions.move_page.submit_button.default"),
          loading: t("page_actions.move_page.submit_button.loading"),
        }}
        variant="primary"
      />
    </MovePageContext.Provider>
  );
});
