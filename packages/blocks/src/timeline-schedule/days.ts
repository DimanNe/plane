/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TDay } from "./types";

const MILLISECONDS_PER_DAY = 86_400_000;

/** Days are counted from 1970-01-01, so that the difference of two day numbers is a number of days. */
export const toDayNumber = (day: TDay): number => Date.parse(day) / MILLISECONDS_PER_DAY;

export const toDay = (dayNumber: number): TDay => new Date(dayNumber * MILLISECONDS_PER_DAY).toISOString().slice(0, 10);
