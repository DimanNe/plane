/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/** An emoji as the editor's emoji data describes it: `name` is the shortcode stored in a description. */
export type TEmojiWithShortcodes = {
  name: string;
  shortcodes: string[];
  tags: string[];
};

// How well the text typed after ":" matches an emoji, best first. People type the start of a shortcode, or of one
// of its words (`:umb` for umbrella, and then for beach_umbrella), as in Slack and Linear; tags are looser words
// such as "rain", so they come last.
const MATCH_OF_WHOLE_SHORTCODE = 0;
const MATCH_OF_START_OF_SHORTCODE = 1;
const MATCH_OF_START_OF_WORD_OF_SHORTCODE = 2;
const MATCH_OF_START_OF_TAG = 3;

type TEmojiWords<T> = {
  emoji: T;
  shortcodes: string[];
  wordsOfShortcodes: string[][];
  tags: string[];
};

type TEmojiMatch<T> = {
  emoji: T;
  match: number;
  shortcodeLength: number;
  order: number;
};

// The words are made once for a list of emojis, at its first query, not on every key typed after ":".
const WORDS_OF_EMOJI_LISTS = new WeakMap<readonly TEmojiWithShortcodes[], TEmojiWords<TEmojiWithShortcodes>[]>();

function getWordsOfEmojis<T extends TEmojiWithShortcodes>(emojis: readonly T[]): TEmojiWords<T>[] {
  const known = WORDS_OF_EMOJI_LISTS.get(emojis);
  if (known) return known as TEmojiWords<T>[];
  const words = emojis.map((emoji) => {
    const shortcodes = [...new Set([emoji.name, ...emoji.shortcodes].map((shortcode) => shortcode.toLowerCase()))];
    return {
      emoji,
      shortcodes,
      wordsOfShortcodes: shortcodes.map((shortcode) => shortcode.split("_")),
      tags: emoji.tags.map((tag) => tag.toLowerCase()),
    };
  });
  WORDS_OF_EMOJI_LISTS.set(emojis, words);
  return words;
}

function matchEmojiToQuery<T>(words: TEmojiWords<T>, query: string, order: number): TEmojiMatch<T> | undefined {
  let best: TEmojiMatch<T> | undefined;
  words.shortcodes.forEach((shortcode, index) => {
    const match =
      shortcode === query
        ? MATCH_OF_WHOLE_SHORTCODE
        : shortcode.startsWith(query)
          ? MATCH_OF_START_OF_SHORTCODE
          : words.wordsOfShortcodes[index].some((word) => word.startsWith(query))
            ? MATCH_OF_START_OF_WORD_OF_SHORTCODE
            : undefined;
    if (match === undefined) return;
    if (!best || match < best.match || (match === best.match && shortcode.length < best.shortcodeLength)) {
      best = { emoji: words.emoji, match, shortcodeLength: shortcode.length, order };
    }
  });
  if (!best && words.tags.some((tag) => tag.startsWith(query))) {
    best = { emoji: words.emoji, match: MATCH_OF_START_OF_TAG, shortcodeLength: 0, order };
  }
  return best;
}

/**
 * The emojis offered for the text typed after ":", best match first, at most `limit`. Of two that match alike, the
 * one whose matching shortcode is shorter is nearer to what was typed (`:smile` is smile before smiley), and then
 * the order of `emojis` decides.
 */
export function findEmojisMatchingQuery<T extends TEmojiWithShortcodes>(
  emojis: readonly T[],
  query: string,
  limit: number
): T[] {
  const lowerCaseQuery = query.toLowerCase();
  const matches: TEmojiMatch<T>[] = [];
  getWordsOfEmojis(emojis).forEach((words, order) => {
    const match = matchEmojiToQuery(words, lowerCaseQuery, order);
    if (match) matches.push(match);
  });
  return matches
    .toSorted((a, b) => a.match - b.match || a.shortcodeLength - b.shortcodeLength || a.order - b.order)
    .slice(0, limit)
    .map(({ emoji }) => emoji);
}
