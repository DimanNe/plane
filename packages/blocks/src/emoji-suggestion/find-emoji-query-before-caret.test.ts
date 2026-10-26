/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { findEmojiQueryBeforeCaret } from "./find-emoji-query-before-caret";
import type { TEmojiQuery } from "./find-emoji-query-before-caret";

describe("findEmojiQueryBeforeCaret", () => {
  type TCase = { name: string; textBeforeCaret: string; expected: TEmojiQuery | null };
  const cases: TCase[] = [
    {
      name: "a ':' after a space begins a query that ends at the caret",
      textBeforeCaret: "rainy :umb",
      expected: { start: 6, query: "umb" },
    },
    {
      name: "a ':' at the start of the text begins a query",
      textBeforeCaret: ":umb",
      expected: { start: 0, query: "umb" },
    },
    {
      name: "a ':' alone begins an empty query",
      textBeforeCaret: "rainy :",
      expected: { start: 6, query: "" },
    },
    {
      name: "a query may hold signs that a shortcode has",
      textBeforeCaret: "ok :+1",
      expected: { start: 3, query: "+1" },
    },
    {
      name: "a ':' inside a time begins no query",
      textBeforeCaret: "at 10:30",
      expected: null,
    },
    {
      name: "a ':' inside an address begins no query",
      textBeforeCaret: "see http://x",
      expected: null,
    },
    {
      name: "a ':' between two letters begins no query",
      textBeforeCaret: "a:b",
      expected: null,
    },
    {
      name: "a ':' after another ':' begins no query",
      textBeforeCaret: "see ::",
      expected: null,
    },
    {
      name: "a space typed after the query ends it",
      textBeforeCaret: "rainy :umb ",
      expected: null,
    },
    {
      name: "a ':' after a tab begins no query, as in the editor, which takes a space only",
      textBeforeCaret: "rainy\t:umb",
      expected: null,
    },
    {
      name: "a ':' at the end of a word ends the query, as in :smile:",
      textBeforeCaret: "so :smile:",
      expected: null,
    },
    {
      name: "a text without ':' has no query",
      textBeforeCaret: "rainy day",
      expected: null,
    },
  ];

  it.each(cases)("$name", ({ textBeforeCaret, expected }) => {
    const actual = findEmojiQueryBeforeCaret(textBeforeCaret);

    expect(actual).toEqual(expected);
  });
});
