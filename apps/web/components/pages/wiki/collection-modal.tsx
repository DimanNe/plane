/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { FormEvent } from "react";
import { useState } from "react";
import type { LucideIcon } from "lucide-react";
// plane imports
import { EPageAccess } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogHeading,
  DialogInfo,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { InputField } from "@makeplane/propel/components/input-field";
import { FolderOutline, GlobeOutline, LockOutline } from "@makeplane/propel/icons";
import type { ChangeHandlerPayload } from "@plane/blocks/emoji-icon-picker";
import { EmojiPicker, Logo } from "@plane/blocks/emoji-icon-picker";
import type { ISvgIcons } from "@plane/blocks/icons";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TLogoProps, TPageCollection } from "@plane/types";
// components
import { AccessField } from "@/components/common/access-field";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { usePlatformOS } from "@/hooks/use-platform-os";

const COLLECTION_ACCESS_SPECIFIERS: {
  key: EPageAccess;
  i18n_label: string;
  icon: LucideIcon | React.FC<ISvgIcons>;
}[] = [
  { key: EPageAccess.PUBLIC, i18n_label: "common.access.public", icon: GlobeOutline },
  { key: EPageAccess.PRIVATE, i18n_label: "common.access.private", icon: LockOutline },
];

type Props = {
  // the collection to edit; a collection is created when there is none
  collection?: TPageCollection;
  onClose: () => void;
};

export function WikiCollectionModal(props: Props) {
  const { collection, onClose } = props;
  // states
  const [name, setName] = useState(collection?.name ?? "");
  const [logoProps, setLogoProps] = useState<TLogoProps | undefined>(collection?.logo_props);
  const [access, setAccess] = useState(EPageAccess.PUBLIC);
  const [isEmojiPickerOpen, setIsEmojiPickerOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  const { isMobile } = usePlatformOS();
  // store hooks
  const { createCollection, updateCollection } = usePageStore(EPageStoreType.WORKSPACE);
  // derived values
  const i18n_access_label = COLLECTION_ACCESS_SPECIFIERS.find((specifier) => specifier.key === access)?.i18n_label;
  const isNameTooLong = name.length > 255;

  const handleLogoChange = (value: ChangeHandlerPayload) => {
    let logoValue = {};
    if (value?.type === "emoji") logoValue = { value: value.value, url: undefined };
    else if (value?.type === "icon") logoValue = value.value;

    setLogoProps({ in_use: value?.type, [value?.type]: logoValue });
    setIsEmojiPickerOpen(false);
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      if (collection) await updateCollection(collection.id, { name: name.trim(), logo_props: logoProps });
      else await createCollection({ name: name.trim(), logo_props: logoProps, access });
      setToast({
        type: "success",
        title: t("toast.success"),
        message: t(collection ? "wiki_collections.toasts.renamed" : "wiki_collections.toasts.created"),
      });
      onClose();
    } catch {
      setToast({
        type: "error",
        title: t("toast.error"),
        message: t(collection ? "wiki_collections.toasts.rename_error" : "wiki_collections.toasts.create_error"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent size="md">
        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <DialogMain>
            <DialogHeader>
              <DialogHeading>
                <DialogTitle>
                  {t(collection ? "wiki_collections.edit_modal.title" : "wiki_collections.create_modal.title")}
                </DialogTitle>
              </DialogHeading>
            </DialogHeader>
            <DialogBody tabIndex={0}>
              <div className="flex h-9 w-full items-start gap-2">
                <EmojiPicker
                  isOpen={isEmojiPickerOpen}
                  handleToggle={setIsEmojiPickerOpen}
                  className="flex flex-shrink-0 items-center justify-center"
                  buttonClassName="flex items-center justify-center rounded-md bg-layer-2 hover:bg-layer-2-hover"
                  label={
                    <span className="grid h-9 w-9 place-items-center rounded-md">
                      {logoProps?.in_use ? (
                        <Logo logo={logoProps} size={18} type="lucide" />
                      ) : (
                        <FolderOutline className="h-4 w-4 text-tertiary" />
                      )}
                    </span>
                  }
                  onChange={handleLogoChange}
                  defaultIconColor={logoProps?.in_use === "icon" ? logoProps.icon?.color : undefined}
                  defaultOpen={logoProps?.in_use === "emoji" ? "emoji" : "icon"}
                />
                <div className="w-full flex-grow space-y-1">
                  <InputField
                    id="name"
                    type="text"
                    size="2xl"
                    orientation="vertical"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={t(
                      collection
                        ? "wiki_collections.form.name_placeholder_edit"
                        : "wiki_collections.form.name_placeholder_create"
                    )}
                    error={isNameTooLong ? t("wiki_collections.form.name_max_length") : undefined}
                    required
                    // the name is the dialog's only text field; focus it on open as the page form does
                    // oxlint-disable-next-line jsx_a11y/no-autofocus
                    autoFocus
                  />
                </div>
              </div>
            </DialogBody>
          </DialogMain>
          <DialogActions>
            {!collection && (
              <DialogInfo>
                <div className="flex items-center gap-2">
                  <AccessField
                    onChange={setAccess}
                    value={access}
                    accessSpecifiers={COLLECTION_ACCESS_SPECIFIERS}
                    isMobile={isMobile}
                  />
                  <h6 className="text-11 font-medium">{t(i18n_access_label || "")}</h6>
                </div>
              </DialogInfo>
            )}
            <Button variant="secondary" size="md" stretch="auto" label={t("cancel")} onClick={onClose} />
            <Button
              variant="primary"
              size="md"
              stretch="auto"
              type="submit"
              label={t(collection ? "save" : "wiki_collections.create_modal.submit")}
              loading={isSubmitting}
              disabled={!name.trim() || isNameTooLong}
            />
          </DialogActions>
        </form>
      </DialogContent>
    </Dialog>
  );
}
