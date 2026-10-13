/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { Row } from "@plane/blocks/layout";
import { cn } from "@plane/utils";
// hooks
import { useAppTheme } from "@/hooks/store/use-app-theme";
// local imports
import { TITLE_TEXT_SIZES } from "./block-title";

type Props = {
  nestingLevel: number;
  isCompact: boolean;
};

/**
 * What stands in a row's place while the list does not draw the row: far from the visible part it draws none.
 * The place must be exactly as high as it is with the row drawn. One that changed its height moved every row
 * below it: the list shifted under the pointer while it was scrolled, and a row the list had just scrolled to
 * was no longer where it had been.
 *
 * So this has the row's own box (block.tsx), and in it something as high as each thing that gives a drawn row
 * its height: a line of the title's text, the chip after the title, and the values, which are scaled with the
 * level as the row scales them.
 */
export const IssueBlockStandIn = observer(function IssueBlockStandIn(props: Props) {
  const { nestingLevel, isCompact } = props;
  // hooks
  const { sidebarCollapsed: isSidebarCollapsed } = useAppTheme();
  // derived values
  const titleTextSize = TITLE_TEXT_SIZES[Math.min(nestingLevel, 2)];

  return (
    <Row
      className={cn("flex min-h-11 flex-col gap-3 bg-surface-1 py-3", {
        "min-h-9 py-2": isCompact,
        "md:flex-row md:items-center": isSidebarCollapsed,
        "lg:flex-row lg:items-center": !isSidebarCollapsed,
      })}
    >
      <div className="flex w-full items-center gap-3">
        <span className="h-5 w-10 rounded-sm bg-surface-2" />
        <p className={cn("w-52 rounded-sm bg-surface-2", titleTextSize)}>&nbsp;</p>
      </div>
      <div
        className="flex flex-shrink-0 items-center gap-2"
        style={{ zoom: `calc(var(--${titleTextSize}) / var(--${TITLE_TEXT_SIZES[0]}))` }}
      >
        <span className="h-5 w-16 rounded-sm bg-surface-2" />
        <span className="h-5 w-16 rounded-sm bg-surface-2" />
        <span className="h-5 w-5 rounded-sm bg-surface-2" />
      </div>
    </Row>
  );
});
