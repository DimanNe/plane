/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { setToast } from "@plane/blocks/toast";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { useTranslation } from "@plane/i18n";
import type { TIdentifierTextProps, TIdentifierTextVariant, TIssueIdentifierSize } from "@plane/types";
import { cn, copyTextToClipboard } from "@plane/utils";

const SIZE_MAP: Record<TIssueIdentifierSize, string> = {
  xs: "text-caption-sm-regular",
  sm: "text-caption-sm-medium",
  md: "text-caption-md-medium",
  lg: "text-caption-lg-medium",
};

const VARIANT_MAP: Record<TIdentifierTextVariant, string> = {
  default: "text-tertiary",
  secondary: "text-secondary",
  tertiary: "text-tertiary",
  primary: "text-primary",
  "primary-subtle": "text-primary/80",
  success: "text-success-primary",
};

export function IdentifierText(props: TIdentifierTextProps) {
  const { identifier, enableClickToCopyIdentifier = false, size = "lg", variant = "default" } = props;
  // plane hooks
  const { t } = useTranslation();
  // handlers
  const handleCopyIssueIdentifier = () => {
    if (enableClickToCopyIdentifier) {
      // FOR_REVIEWER: the id stays upstream's <button>, inside which Chrome starts no text selection: a drag that
      // begins on the id selects nothing and copies it as a click does; one that begins beside it selects it. A
      // <span role="button"> could be selected, but would need Enter and Space of its own, next to the keys of the
      // view that PLANE-89 changes.
      copyTextToClipboard(identifier)
        .then(() => {
          setToast({
            type: "success",
            title: t("common.id_copied"),
            message: t("common.id_copied_to_clipboard", { id: identifier }),
          });
          return;
        })
        .catch(() => {
          console.error("Failed to copy work item ID");
        });
    }
  };

  const textSizeClassName = SIZE_MAP[size];
  const variantClassName = VARIANT_MAP[variant];

  return (
    <Tooltip label="Click to copy" disabled={!enableClickToCopyIdentifier}>
      <button
        type="button"
        className={cn("text-12 font-medium whitespace-nowrap text-tertiary", textSizeClassName, variantClassName, {
          "cursor-pointer": enableClickToCopyIdentifier,
        })}
        onClick={handleCopyIssueIdentifier}
        disabled={!enableClickToCopyIdentifier}
      >
        {identifier}
      </button>
    </Tooltip>
  );
}
