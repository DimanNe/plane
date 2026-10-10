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

type Props = {
  isEpic: boolean;
  onClick: () => void;
};

/**
 * The chip after the name and the count of a list group. It stands in the part of the header that folds the
 * group on a click, so its own click must not reach that part.
 */
export function ListGroupQuickAddChip(props: Props) {
  const { isEpic, onClick } = props;
  // hooks
  const { t } = useTranslation();

  return (
    <span className="flex shrink-0 pl-2">
      <Pill
        size="xs"
        variant="outline"
        startIcon={<Icon icon={AddOutline} />}
        label={t(isEpic ? "epic.new" : "issue.new")}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      />
    </span>
  );
}
