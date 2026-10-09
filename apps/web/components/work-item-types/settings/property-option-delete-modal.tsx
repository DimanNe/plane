/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Button } from "@makeplane/propel/components/button";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { Input, InputGroup } from "@makeplane/propel/components/input";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { TWorkItemPropertyOption } from "@plane/types";

type Props = {
  // an option that work items have selected, with their count
  option: TWorkItemPropertyOption;
  onClose: () => void;
  onConfirm: () => Promise<void>;
};

export function WorkItemPropertyOptionDeleteModal(props: Props) {
  const { option, onClose, onConfirm } = props;
  // states
  const [confirmation, setConfirmation] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // derived values
  const i18nPrefix = "work_item_types.settings.properties.attributes.option.delete_confirmation";
  const confirmationWord = t("common.confirm");

  const handleConfirm = async () => {
    setIsDeleting(true);
    await onConfirm().finally(() => setIsDeleting(false));
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !isDeleting) onClose();
      }}
    >
      <DialogContent size="sm">
        <DialogMain>
          <DialogHeader>
            <DialogHeading>
              <DialogTitle>{t(`${i18nPrefix}.title`)}</DialogTitle>
            </DialogHeading>
          </DialogHeader>
          <DialogBody>
            <div className="flex flex-col gap-3 text-13 text-secondary">
              <p>{t(`${i18nPrefix}.description`, { count: option.work_item_count ?? 0, name: option.name })}</p>
              <p>{t(`${i18nPrefix}.input_label`, { word: confirmationWord })}</p>
              <InputGroup size="lg">
                <Input
                  size="lg"
                  type="text"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  placeholder={confirmationWord}
                  aria-label={confirmationWord}
                  autoComplete="off"
                />
              </InputGroup>
            </div>
          </DialogBody>
        </DialogMain>
        <DialogActions>
          <Button variant="secondary" size="md" stretch="auto" label={t("common.cancel")} onClick={onClose} />
          <Button
            variant="danger"
            size="md"
            stretch="auto"
            label={t("common.remove")}
            loading={isDeleting}
            disabled={confirmation !== confirmationWord}
            onClick={handleConfirm}
          />
        </DialogActions>
      </DialogContent>
    </Dialog>
  );
}
