/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { EPageAccess } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
import { Combobox, ComboboxItem, ComboboxList, ComboboxSearch } from "@makeplane/propel/components/combobox";
import { Dialog, DialogActions, DialogContent, DialogMain, DialogTitle } from "@makeplane/propel/components/dialog";
import { PagesOutline } from "@makeplane/propel/icons";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import { getPageName } from "@plane/utils";
// components
import { SwitcherIcon } from "@/components/common/switcher-label";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

type Props = {
  collectionId: string;
  isOpen: boolean;
  onClose: () => void;
};

export const AddExistingPagesModal = observer(function AddExistingPagesModal(props: Props) {
  const { collectionId, isOpen, onClose } = props;
  // states
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedPageIds, setSelectedPageIds] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { collectionIds, getPageById, getCollectionById, getTopLevelPageIds, movePage } = usePageStore(
    EPageStoreType.WORKSPACE
  );
  // derived values
  const title = t("wiki_collections.menu.add_existing_page");
  // the top level pages of the other collections and the private pages outside collections
  const pageIds = [null, ...collectionIds]
    .filter((id) => id !== collectionId)
    .flatMap((id) => getTopLevelPageIds(id))
    .filter((pageId) => getPageById(pageId)?.canCurrentUserMovePage);
  const filteredPageIds = pageIds.filter((pageId) =>
    getPageName(getPageById(pageId)?.name).toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleClose = () => {
    onClose();
    setSearchTerm("");
    setSelectedPageIds([]);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      await Promise.all(selectedPageIds.map((pageId) => movePage(pageId, { collection_id: collectionId })));
      setToast({
        type: "success",
        title: t("toast.success"),
        message: t("wiki_collections.add_existing_page_modal.success_message", { count: selectedPageIds.length }),
      });
      handleClose();
    } catch {
      setToast({
        type: "error",
        title: t("toast.error"),
        message: t("wiki_collections.add_existing_page_modal.error_message"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent size="sm">
        {/* The search field is the only visible chrome, so the dialog's accessible name is carried
            by a visually hidden title. */}
        <div className="sr-only">
          <DialogTitle>{title}</DialogTitle>
        </div>
        {/* `inline open` is Base UI's "list without a popup" mode: the dialog is the surface, so the
            list renders in place. */}
        <Combobox<string, true>
          inline
          multiple
          open={isOpen}
          onOpenChange={(open) => {
            if (!open) handleClose();
          }}
          value={selectedPageIds}
          onValueChange={setSelectedPageIds}
          inputValue={searchTerm}
          onInputValueChange={(next, details) => {
            // Base UI clears the query itself after every pick in multiple mode
            if (details.reason === "input-clear") return;
            setSearchTerm(next);
          }}
        >
          <ComboboxSearch
            placeholder={t("wiki_collections.add_existing_page_modal.search_placeholder")}
            aria-label={title}
          />
          <DialogMain>
            <p className="text-11 text-tertiary">
              {t(
                getCollectionById(collectionId)?.access === EPageAccess.PRIVATE
                  ? "wiki_collections.add_existing_page_modal.private_hint"
                  : "wiki_collections.add_existing_page_modal.public_hint"
              )}
            </p>
            <div className="vertical-scrollbar scrollbar-md max-h-80 scroll-py-2 overflow-x-hidden overflow-y-auto overscroll-contain text-primary">
              {filteredPageIds.length === 0 ? (
                <p className="px-3 py-8 text-center text-13 text-placeholder">
                  {t(
                    pageIds.length === 0
                      ? "wiki_collections.add_existing_page_modal.no_pages_available"
                      : "wiki_collections.add_existing_page_modal.no_pages_found"
                  )}
                </p>
              ) : (
                <ComboboxList aria-label={title}>
                  {filteredPageIds.map((pageId) => (
                    <ComboboxItem
                      key={pageId}
                      value={pageId}
                      selection="checkbox"
                      label={getPageName(getPageById(pageId)?.name)}
                      icon={
                        <SwitcherIcon logo_props={getPageById(pageId)?.logo_props} LabelIcon={PagesOutline} size={16} />
                      }
                    />
                  ))}
                </ComboboxList>
              )}
            </div>
          </DialogMain>
        </Combobox>
        <DialogActions>
          <Button variant="secondary" size="md" stretch="auto" label={t("cancel")} onClick={handleClose} />
          <Button
            variant="primary"
            size="md"
            stretch="auto"
            label={t("wiki_collections.add_existing_page_modal.submit")}
            onClick={() => void handleSubmit()}
            loading={isSubmitting}
            disabled={selectedPageIds.length === 0}
          />
        </DialogActions>
      </DialogContent>
    </Dialog>
  );
});
