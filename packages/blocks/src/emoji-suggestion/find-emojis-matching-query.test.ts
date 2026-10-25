/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { findEmojisMatchingQuery } from "./find-emojis-matching-query";
import type { TEmojiWithShortcodes } from "./find-emojis-matching-query";

// Emojis of the editor's data, in its order.
const EMOJIS: TEmojiWithShortcodes[] = [
  { name: "beach_umbrella", shortcodes: ["beach", "beach_with_umbrella"], tags: ["beach", "umbrella"] },
  { name: "closed_umbrella", shortcodes: ["closed_umbrella"], tags: ["clothing", "rain", "umbrella"] },
  { name: "open_umbrella", shortcodes: ["umbrella"], tags: ["clothing", "rain"] },
  { name: "umbrella", shortcodes: ["umbrella_with_rain"], tags: ["clothing", "drop", "rain", "umbrella"] },
  {
    name: "parasol_on_ground",
    shortcodes: ["beach_umbrella", "umbrella_on_ground"],
    tags: ["rain", "sun", "umbrella"],
  },
  { name: "rainbow", shortcodes: ["rainbow"], tags: ["rain"] },
  { name: "cloud_with_rain", shortcodes: ["cloud_with_rain", "rainy"], tags: ["cloud", "rain"] },
  { name: "+1", shortcodes: ["+1", "thumbsup", "yes"], tags: ["+1", "hand", "thumb", "up"] },
  { name: "-1", shortcodes: ["-1", "no", "thumbsdown"], tags: ["-1", "down", "hand", "thumb"] },
  { name: "sweat_smile", shortcodes: ["grinning_face_with_sweat", "sweat_smile"], tags: ["face", "smile", "sweat"] },
  { name: "smiley", shortcodes: ["grinning_face_with_big_eyes", "smiley"], tags: ["face", "mouth", "open", "smile"] },
  { name: "smile", shortcodes: ["grinning_face_with_closed_eyes", "smile"], tags: ["eye", "face", "open", "smile"] },
];

describe("findEmojisMatchingQuery", () => {
  type TCase = { name: string; query: string; limit: number; expected: string[] };
  const cases: TCase[] = [
    {
      name: "a shortcode that starts with the text comes before one that only has a word that starts with it",
      query: "umb",
      limit: 5,
      expected: ["open_umbrella", "umbrella", "parasol_on_ground", "beach_umbrella", "closed_umbrella"],
    },
    {
      name: "the whole shortcode comes first, then the shorter of the shortcodes that start with the text",
      query: "smile",
      limit: 5,
      expected: ["smile", "smiley", "sweat_smile"],
    },
    {
      name: "an emoji is found by the name it is stored under",
      query: "+1",
      limit: 5,
      expected: ["+1"],
    },
    {
      name: "an emoji is found by any of its shortcodes",
      query: "thumbs",
      limit: 5,
      expected: ["+1", "-1"],
    },
    {
      name: "a tag matches after every shortcode that matches, in the order of the data",
      query: "rain",
      limit: 10,
      expected: ["cloud_with_rain", "rainbow", "umbrella", "closed_umbrella", "open_umbrella", "parasol_on_ground"],
    },
    {
      name: "capitals match as small letters, and the list is cut at the limit, best first",
      query: "UMB",
      limit: 2,
      expected: ["open_umbrella", "umbrella"],
    },
    {
      name: "the text in the middle of a word matches nothing",
      query: "mbrella",
      limit: 5,
      expected: [],
    },
  ];

  it.each(cases)("$name", ({ query, limit, expected }) => {
    const actual = findEmojisMatchingQuery(EMOJIS, query, limit).map(({ name }) => name);

    expect(actual).toEqual(expected);
  });
});
