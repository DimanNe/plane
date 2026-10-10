/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// the distance in the manual order between a work item that gets the first or the last place and the one beside it
export const SORT_ORDER_STEP = 1000;

/** The ids with one of them moved before another, or to the end. */
export const moveBefore = (ids: string[], id: string, beforeId: string | undefined) => {
  const others = ids.filter((other) => other !== id);
  const index = beforeId === undefined ? -1 : others.indexOf(beforeId);
  return index === -1 ? [...others, id] : [...others.slice(0, index), id, ...others.slice(index)];
};

/**
 * The places in the manual order that put work items in the order they are given in, when their places are
 * `sortOrders` now. A place is saved with one request per work item, so as few as can be change: the work items
 * of the longest run whose places ascend already keep theirs, and the others go between their kept neighbours.
 * No two places are equal: work items that share a place come in an order the page does not decide.
 */
export const getManualOrder = (sortOrders: number[]): number[] => {
  // the length of the longest ascending run that ends with each work item, and the one before it in that run
  const lengths = sortOrders.map(() => 1);
  const previous = sortOrders.map(() => -1);
  let last = sortOrders.length - 1;
  sortOrders.forEach((sortOrder, index) => {
    for (let before = 0; before < index; before++)
      if (sortOrders[before] < sortOrder && lengths[before] >= lengths[index]) {
        lengths[index] = lengths[before] + 1;
        previous[index] = before;
      }
    if (lengths[index] > lengths[last]) last = index;
  });
  const kept = new Set<number>();
  for (let index = last; index >= 0; index = previous[index]) kept.add(index);

  const places = [...sortOrders];
  for (let start = 0; start < places.length; start++) {
    if (kept.has(start)) continue;
    let end = start;
    while (end < places.length && !kept.has(end)) end++;
    const count = end - start;
    const after = end < places.length ? places[end] : undefined;
    const from = start > 0 ? places[start - 1] : (after ?? 0) - (count + 1) * SORT_ORDER_STEP;
    const to = after ?? from + (count + 1) * SORT_ORDER_STEP;
    for (let index = 0; index < count; index++)
      places[start + index] = from + ((to - from) * (index + 1)) / (count + 1);
    start = end;
  }
  return places;
};
