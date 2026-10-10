/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/** One debounce for every server-side option search (paginated lists, menu sources). */
export const SELECT_SEARCH_DEBOUNCE_MS = 300;

/** Estimated height of a legacy `renderOption` row (py-1.5 + text-13), which sets its own box. */
export const MENU_ROW_HEIGHT = 32;

/** Estimated height of Select's standard option row — propel `ComboboxItem`'s fixed single-line `h-7`. */
export const SELECT_OPTION_ROW_HEIGHT = 28;

/**
 * The most of the window's height that Select's option list takes. The list is shorter when its popup has
 * less room than that: the popup never passes the edge of the window, and the list gives way inside it.
 */
export const SELECT_LIST_MAX_SHARE_OF_WINDOW_HEIGHT = 1 / 3;

/** Bounded, scrollable option-list container inside a flyout panel. */
export const MENU_LIST_CLASSNAME = "max-h-48 overflow-y-auto vertical-scrollbar scrollbar-sm p-1";
