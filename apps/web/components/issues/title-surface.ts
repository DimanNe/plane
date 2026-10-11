/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * A work item's title and its description are both plain text of nearly one size; without a surface of its own
 * the title reads as the first lines of the description. The surface is wider than the text by its padding, so
 * the title keeps the left edge of the description.
 */
export const ISSUE_TITLE_SURFACE_CLASSNAME = "-mx-3 rounded-md bg-layer-1 px-3 py-2";

/**
 * A line between the title's surface and the description, with room on both sides: the surface alone left the
 * two too close to read as two things. The line is as wide as the surface.
 */
export const ISSUE_TITLE_SEPARATOR_CLASSNAME = "-mx-3 mt-4 mb-2 border-subtle";
