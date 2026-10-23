/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { AddOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";

type Props = {
  isEpic: boolean;
  onClick: () => void;
};

/**
 * The "+" after the name and the count of a list group, which opens the dialog for a new work item of the group. It
 * stands in the part of the header that folds the group on a click, so its own click must not reach that part.
 */
export function ListGroupNewWorkItemButton(props: Props) {
  const { isEpic, onClick } = props;
  // hooks
  const { t } = useTranslation();

  return (
    <button
      type="button"
      aria-label={t(isEpic ? "epic.new" : "issue.new")}
      className="ml-2 flex h-5 w-5 flex-shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-xs transition-all hover:bg-layer-1"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <AddOutline width={14} />
    </button>
  );
}
