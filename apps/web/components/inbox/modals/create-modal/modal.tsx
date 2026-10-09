/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
// plane imports
import { Dialog, DialogContent } from "@makeplane/propel/components/dialog";
// local imports
import { InboxIssueCreateRoot } from "./create-root";
import { useUntouchedDialog } from "@/hooks/use-untouched-dialog";

type TInboxIssueCreateModalRoot = {
  workspaceSlug: string;
  projectId: string;
  modalState: boolean;
  handleModalClose: () => void;
};

export function InboxIssueCreateModalRoot(props: TInboxIssueCreateModalRoot) {
  const { workspaceSlug, projectId, modalState, handleModalClose } = props;
  // states
  const [isDuplicateModalOpen, setIsDuplicateModalOpen] = useState(false);
  // handlers
  const handleDuplicateIssueModal = (value: boolean) => setIsDuplicateModalOpen(value);

  const { popupRef, shouldIgnoreOutsidePress } = useUntouchedDialog();

  return (
    <Dialog
      open={modalState}
      // A window-level Escape listener closed the legacy modal; Base UI's Escape is now that single
      // Escape path. An outside press dismisses it while nothing was changed in it.
      onOpenChange={(open, eventDetails) => {
        if (!open && !shouldIgnoreOutsidePress(eventDetails)) {
          handleModalClose();
          setIsDuplicateModalOpen(false);
        }
      }}
    >
      <DialogContent size="lg" ref={popupRef}>
        <InboxIssueCreateRoot
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          handleModalClose={handleModalClose}
          isDuplicateModalOpen={isDuplicateModalOpen}
          handleDuplicateIssueModal={handleDuplicateIssueModal}
        />
      </DialogContent>
    </Dialog>
  );
}
