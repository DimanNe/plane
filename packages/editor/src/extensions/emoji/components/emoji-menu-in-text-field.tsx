/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { autoUpdate, computePosition, flip, shift } from "@floating-ui/dom";
import type { VirtualElement } from "@floating-ui/dom";
import { memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { createPortal } from "react-dom";
// plane imports
import { findEmojiQueryBeforeCaret, findEmojisMatchingQuery } from "@plane/blocks/emoji-suggestion";
import type { TEmojiQuery } from "@plane/blocks/emoji-suggestion";
// helpers
import type { CommandListInstance } from "@/helpers/tippy";
import { DROPDOWN_NAVIGATION_KEYS } from "@/helpers/tippy";
// local imports
import { EmojiExtension } from "../extension";
import { EMOJI_MENU_LENGTH, EmojisListDropdown, isEmojiMenuShown } from "./emojis-list";
import type { EmojiItem } from "./emojis-list";

type TTextField = HTMLInputElement | HTMLTextAreaElement;

// The editor's own list, so that a title offers what a description does, and the words of its shortcodes are indexed
// once for both (find-emojis-matching-query.ts).
const EMOJIS = EmojiExtension.options.emojis as EmojiItem[];

// the styles that decide where a field draws each character of its text
const TEXT_LAYOUT_STYLES = [
  "box-sizing",
  "width",
  "border-top-width",
  "border-right-width",
  "border-bottom-width",
  "border-left-width",
  "border-style",
  "padding-top",
  "padding-right",
  "padding-bottom",
  "padding-left",
  "font-family",
  "font-size",
  "font-style",
  "font-variant",
  "font-weight",
  "font-stretch",
  "line-height",
  "letter-spacing",
  "word-spacing",
  "text-indent",
  "text-transform",
  "text-align",
  "tab-size",
  "word-break",
  "overflow-wrap",
];

type TCaretInField = {
  left: number;
  top: number;
  height: number;
};

/**
 * The editor puts its menu at the caret, but a page cannot ask a text field where it draws its caret. So the text up
 * to the caret is laid out once more, unseen, in a box with the field's place, width and text styles; where that text
 * ends is where the field draws the caret. An input draws its one line in the middle of the box inside its padding.
 * The caret is measured from the field's corner, where it stays until the text changes, so that the menu follows a
 * page that scrolls without laying out the text again.
 */
const measureCaretInField = (field: TTextField): TCaretInField => {
  const style = getComputedStyle(field);
  const fieldRect = field.getBoundingClientRect();
  const copy = document.createElement("div");
  TEXT_LAYOUT_STYLES.forEach((name) => copy.style.setProperty(name, style.getPropertyValue(name)));
  Object.assign(copy.style, {
    position: "fixed",
    left: `${fieldRect.left}px`,
    top: `${fieldRect.top}px`,
    visibility: "hidden",
    whiteSpace: field instanceof HTMLTextAreaElement ? "pre-wrap" : "pre",
  });
  copy.textContent = field.value.slice(0, field.selectionEnd ?? 0);
  const caret = document.createElement("span");
  // a character of no width, so that the caret has the height of a line where the text is empty
  caret.textContent = "\u200b";
  copy.append(caret);
  document.body.append(copy);
  const caretRect = caret.getBoundingClientRect();
  copy.remove();
  const left = caretRect.left - fieldRect.left - field.scrollLeft;
  if (field instanceof HTMLTextAreaElement)
    return { left, top: caretRect.top - fieldRect.top - field.scrollTop, height: caretRect.height };
  const above = parseFloat(style.borderTopWidth) + parseFloat(style.paddingTop);
  const below = parseFloat(style.borderBottomWidth) + parseFloat(style.paddingBottom);
  return { left, top: above + (fieldRect.height - above - below - caretRect.height) / 2, height: caretRect.height };
};

const isSameEmojiQuery = (a: TEmojiQuery | null, b: TEmojiQuery | null) =>
  a?.start === b?.start && a?.query === b?.query;

type Props = {
  fieldRef: RefObject<TTextField | null>;
};

/**
 * The editor's emoji menu for a plain text field, such as a work item's title, which is no editor: ":" and the start
 * of a shortcode offer the same emojis, drawn by the same menu, chosen by the same keys and click, and the emoji takes
 * the place of what was typed, as text of the field. While the menu shows, it takes its keys before the field and the
 * page, where Enter goes on in the description or saves the title, the arrow keys move the caret, and Escape closes
 * the view or ends the editing of the title.
 */
export const EmojiMenuInTextField = memo(function EmojiMenuInTextField(props: Props) {
  const { fieldRef } = props;
  // states
  const [typed, setTyped] = useState<TEmojiQuery | null>(null);
  // the start of the query whose menu Escape or a click beside it closed: typing on there is text, as in the editor
  const [closedAt, setClosedAt] = useState<number | null>(null);
  // refs
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<CommandListInstance>(null);
  // derived values
  // FOR_REVIEWER: no emoji is offered for a ":" alone (isEmojiMenuShown), and every emoji would match it.
  const items = useMemo(
    () => (typed?.query ? (findEmojisMatchingQuery(EMOJIS, typed.query, EMOJI_MENU_LENGTH) as EmojiItem[]) : []),
    [typed]
  );
  const isShown = !!typed && typed.start !== closedAt && isEmojiMenuShown({ items, query: typed.query });

  // On the document, with the field read at each event: the quick add of a work item finds its title only after this
  // menu is in place.
  useEffect(() => {
    const readTyped = (): TEmojiQuery | null => {
      const field = fieldRef.current;
      if (!field || document.activeElement !== field || field.selectionStart !== field.selectionEnd) return null;
      return findEmojiQueryBeforeCaret(field.value.slice(0, field.selectionEnd ?? 0));
    };
    const followField = (event: Event) => {
      if (event.type !== "selectionchange" && event.target !== fieldRef.current) return;
      const next = event.type === "focusout" ? null : readTyped();
      setTyped((previous) => (isSameEmojiQuery(previous, next) ? previous : next));
      setClosedAt((closed) => (next?.start === closed ? closed : null));
    };
    const events = ["input", "selectionchange", "focusin", "focusout"];
    events.forEach((name) => document.addEventListener(name, followField, true));
    return () => events.forEach((name) => document.removeEventListener(name, followField, true));
  }, [fieldRef]);

  // On the window and on the key's way down, before the field and the page, which also listens on the way down (the
  // dialog of a new work item saves on Ctrl+Enter there).
  useEffect(() => {
    if (!isShown || !typed) return undefined;
    const takeMenuKeys = (event: KeyboardEvent) => {
      if (event.target !== fieldRef.current || event.isComposing) return;
      if (![...DROPDOWN_NAVIGATION_KEYS, "Tab", "Escape"].includes(event.key)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (event.key === "Escape") setClosedAt(typed.start);
      else menuRef.current?.onKeyDown({ event });
    };
    window.addEventListener("keydown", takeMenuKeys, true);
    return () => window.removeEventListener("keydown", takeMenuKeys, true);
  }, [isShown, typed, fieldRef]);

  // as the editor places its menu (helpers/floating-ui.ts), at the caret, which moves with every key
  useLayoutEffect(() => {
    const field = fieldRef.current;
    const container = containerRef.current;
    if (!isShown || !field || !container) return undefined;
    const caretInField = measureCaretInField(field);
    const caret: VirtualElement = {
      getBoundingClientRect: () => {
        const fieldRect = field.getBoundingClientRect();
        return new DOMRect(
          fieldRect.left + caretInField.left,
          fieldRect.top + caretInField.top,
          0,
          caretInField.height
        );
      },
      contextElement: field,
    };
    return autoUpdate(caret, container, () => {
      computePosition(caret, container, { placement: "bottom-start", strategy: "fixed", middleware: [shift(), flip()] })
        .then(({ x, y }) => Object.assign(container.style, { left: `${x}px`, top: `${y}px` }))
        .catch((error) => console.error("An error occurred while placing the emoji menu of a text field:", error));
    });
  }, [isShown, typed, fieldRef]);

  const insertEmoji = ({ name }: { name: string }) => {
    const field = fieldRef.current;
    const emoji = items.find((item) => item.name === name)?.emoji;
    if (!field || !typed || !emoji) return;
    const caret = field.selectionEnd ?? field.value.length;
    // As the editor does, a space follows the emoji, in place of one that was there.
    const end = field.value[caret] === " " ? caret + 1 : caret;
    field.setSelectionRange(typed.start, end);
    // FOR_REVIEWER: execCommand is deprecated, but it is the one way to change the text of a field as typing does:
    // the field's own undo takes the emoji back to what was typed, and React and react-hook-form, which keep the
    // titles, hear the change as they hear a key. Setting `value` would do neither.
    document.execCommand("insertText", false, `${emoji} `);
  };

  if (!isShown || !typed) return null;

  return createPortal(
    <div
      ref={containerRef}
      className="fixed z-[100]"
      style={{ width: "max-content" }}
      // A press anywhere on the menu, and on the cover beside it that closes it, leaves the caret in the field: a
      // title edited in place ends when it loses the focus.
      onMouseDownCapture={(event) => event.preventDefault()}
      // and a form that closes when a press lands outside it, as the quick add of a work item, stays open
      data-prevent-outside-click
    >
      <EmojisListDropdown
        ref={menuRef}
        items={items}
        query={typed.query}
        command={insertEmoji}
        onClose={() => setClosedAt(typed.start)}
      />
    </div>,
    document.body
  );
});
