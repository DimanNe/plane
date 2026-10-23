/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * A property that a list shows or not: a chip of the list's tone with lighter text when hidden, and of the accent's
 * when shown, so that what is shown reads at a glance without a box around each, by hue and by lightness.
 */
export const getDisplayPropertyToggleClassName = (isShown: boolean) =>
  `rounded-md px-2 py-0.5 text-11 transition-colors ${
    isShown
      ? "bg-accent-subtle text-accent-primary"
      : "bg-[color:var(--chip-surface,var(--bg-layer-3))] text-placeholder hover:bg-layer-3-hover hover:text-secondary"
  }`;
