/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/** Where the ":" that opens the emoji menu is in a field's text, and the text typed after it up to the caret. */
export type TEmojiQuery = {
  start: number;
  query: string;
};

const isWhitespace = (character: string) => /\s/.test(character);

/**
 * What a plain text field, such as a work item's title, offers emojis for, by the rule of the editor's emoji menu: a
 * ":" at the start of the text or after a space, and what follows it up to the caret, with no space and no other ":".
 * A ":" inside a word, as in 10:30, http://x or a:b, is text. `textBeforeCaret` is the field's text up to the caret.
 */
export function findEmojiQueryBeforeCaret(textBeforeCaret: string): TEmojiQuery | null {
  // FOR_REVIEWER: the editor finds its ":" with customFindSuggestionMatch (packages/editor/src/helpers), as its
  // emoji extension configures it: after a space or at the start of a paragraph, and no space after it. That code
  // reads the editor's document; this is the same rule for the text of a field, with tests of its own.
  let wordStart = textBeforeCaret.length;
  while (wordStart > 0 && textBeforeCaret[wordStart - 1] !== ":" && !isWhitespace(textBeforeCaret[wordStart - 1])) {
    wordStart -= 1;
  }
  const colon = wordStart - 1;
  if (colon < 0 || textBeforeCaret[colon] !== ":") return null;
  if (colon > 0 && textBeforeCaret[colon - 1] !== " ") return null;
  return { start: colon, query: textBeforeCaret.slice(wordStart) };
}
