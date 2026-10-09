/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
// plane imports
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onDelete: () => Promise<void>;
  title: string;
  content: string;
  confirmLabel: string;
  // the prefix of the `success` and `error` toasts, each with a `title` and a `message`
  i18nToastPrefix: string;
  name?: string;
};

/** Asks before a work item type or a property is deleted, and reports how the deletion went. */
export function WorkItemTypeSettingsDeleteModal(props: Props) {
  const { isOpen, onClose, onDelete, title, content, confirmLabel, i18nToastPrefix, name } = props;
  // states
  const [isDeleting, setIsDeleting] = useState(false);
  // plane hooks
  const { t } = useTranslation();

  const handleDelete = async () => {
    setIsDeleting(true);
    const outcome = await onDelete().then(
      () => "success" as const,
      () => "error" as const
    );
    setToast({
      type: outcome,
      title: t(`${i18nToastPrefix}.${outcome}.title`),
      message: t(`${i18nToastPrefix}.${outcome}.message`, { name }),
    });
    setIsDeleting(false);
    if (outcome === "success") onClose();
  };

  return (
    <ConfirmDialog
      isOpen={isOpen}
      handleClose={onClose}
      handleSubmit={handleDelete}
      isSubmitting={isDeleting}
      title={title}
      content={content}
      primaryButtonText={{ loading: t("deleting"), default: confirmLabel }}
    />
  );
}
