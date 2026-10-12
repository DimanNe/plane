/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { cn } from "@plane/utils";

type Props = {
  spacingLeft?: number;
  className?: string;
};

/**
 * The place between two rows of the List layout that a row held over the list would take. Its left end tells the
 * level the row lands on: at the top level the line runs from edge to edge, as the rows do; a line among
 * sub-work items begins where their text begins. An indent at the top level would read as one level down.
 */
export function ListDropLine(props: Props) {
  const { spacingLeft = 0, className } = props;

  return (
    <div
      className={cn("pointer-events-none absolute right-0 z-[2]", { "pl-page-x": spacingLeft > 0 }, className)}
      style={{ left: spacingLeft }}
    >
      <div className="relative h-1 -translate-y-1/2 rounded-full bg-accent-primary before:absolute before:top-1/2 before:left-0 before:size-3 before:-translate-y-1/2 before:rounded-full before:border-[3px] before:border-accent-strong before:bg-surface-1" />
    </div>
  );
}
