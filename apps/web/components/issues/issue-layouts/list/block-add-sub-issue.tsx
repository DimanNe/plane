/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { Icon } from "@makeplane/propel/components/icon";
import { Pill } from "@makeplane/propel/components/pill";
import { AddOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
// hooks
import { useCommandPalette } from "@/hooks/store/use-command-palette";

type Props = {
  issueId: string;
};

/**
 * The chip after the title of a list row, shown while the pointer is over the row
 */
export function IssueBlockAddSubIssue(props: Props) {
  const { issueId } = props;
  // hooks
  const { t } = useTranslation();
  const { toggleCreateIssueModal } = useCommandPalette();

  return (
    // In a right-to-left box, content that does not fit hangs out at the left: where a title fills the row and
    // leaves the chip no room, the chip shows whole over the end of the title.
    <span className="invisible relative z-1 block text-left leading-none whitespace-nowrap [direction:rtl] group-hover/list-block:visible">
      <span className="inline-flex align-middle [direction:ltr]">
        <Pill
          size="xs"
          variant="soft"
          tabIndex={-1}
          startIcon={<Icon icon={AddOutline} />}
          label={t("issue.add.sub_issue")}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleCreateIssueModal(true, undefined, undefined, issueId);
          }}
        />
      </span>
    </span>
  );
}
