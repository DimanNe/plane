/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type * as React from "react";
import type { TContextMenuItem, TContextMenuItemVariant } from "./types";

/** Rows whose `shouldRender` is explicitly `false` never reach the surface. */
export function getRenderableItems(items: TContextMenuItem[] | undefined): TContextMenuItem[] {
  return items?.filter((item) => item.shouldRender !== false) ?? [];
}

/**
 * The row's look. `variant` wins; failing that, a legacy `className` carrying a `text-danger` token
 * still resolves to `danger`, which is how the ~15 quick-action files currently paint their Delete
 * row. Drop this fallback once those call sites pass `variant` instead.
 */
export function resolveItemVariant(item: TContextMenuItem): TContextMenuItemVariant {
  if (item.variant) return item.variant;
  if (item.className?.includes("text-danger")) return "danger";
  return "neutral";
}

/**
 * The popup is portalled, but React events still bubble through the consumer's tree — a card `Link`
 * or `ControlLink` wrapping the menu would otherwise act on every click inside the surface.
 */
export function stopClickPropagation(e: React.MouseEvent) {
  e.stopPropagation();
}

/**
 * A key that stands for an item of an element's right-click menu, such as Delete for "Delete" on a list row, must
 * act only where the menu has that item, and do what the item does. The menu belongs to whoever rendered it, so
 * the key's handler asks the element: the menu of that element answers the event.
 */
export const CONTEXT_MENU_ITEM_EVENT = "plane:context-menu-item";

export type TContextMenuItemRequest = { key: string; shouldRun: boolean };

/** Whether the right-click menu of the element has the item with this key. */
export const hasContextMenuItem = (parent: Element, key: string) =>
  !parent.dispatchEvent(
    new CustomEvent(CONTEXT_MENU_ITEM_EVENT, { detail: { key, shouldRun: false }, cancelable: true })
  );

/** Does what the item with this key does, if the right-click menu of the element has it; tells whether it has. */
export const runContextMenuItem = (parent: Element, key: string) =>
  !parent.dispatchEvent(
    new CustomEvent(CONTEXT_MENU_ITEM_EVENT, { detail: { key, shouldRun: true }, cancelable: true })
  );
