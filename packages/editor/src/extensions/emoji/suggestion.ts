/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { EmojiOptions, EmojiStorage } from "@tiptap/extension-emoji";
import { ReactRenderer } from "@tiptap/react";
import type { Editor } from "@tiptap/react";
import type { SuggestionProps } from "@tiptap/suggestion";
// plane imports
import { findEmojisMatchingQuery } from "@plane/blocks/emoji-suggestion";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// helpers
import { updateFloatingUIFloaterPosition } from "@/helpers/floating-ui";
import type { CommandListInstance } from "@/helpers/tippy";
import { DROPDOWN_NAVIGATION_KEYS } from "@/helpers/tippy";
// local imports
import { EMOJI_MENU_LENGTH, EmojisListDropdown, isEmojiMenuShown } from "./components/emojis-list";
import type { EmojisListDropdownProps, EmojiItem } from "./components/emojis-list";
import type { ExtendedEmojiStorage } from "./emoji";

const DEFAULT_EMOJIS = ["+1", "-1", "smile", "orange_heart", "eyes"];

export const emojiSuggestion: EmojiOptions["suggestion"] = {
  items: ({ editor, query }: { editor: Editor; query: string }): EmojiItem[] => {
    const { emojis } = editor.storage.emoji as EmojiStorage;

    if (query.trim() === "") {
      const defaultEmojis = DEFAULT_EMOJIS.map((name) =>
        emojis.find((emoji) => emoji.shortcodes.includes(name) || emoji.name === name)
      )
        .filter(Boolean)
        .slice(0, 5);
      return defaultEmojis as EmojiItem[];
    }
    return findEmojisMatchingQuery(emojis, query, EMOJI_MENU_LENGTH) as EmojiItem[];
  },

  allowSpaces: false,

  render: () => {
    let component: ReactRenderer<CommandListInstance, EmojisListDropdownProps> | null = null;
    let cleanup: () => void = () => {};
    let editorRef: Editor | null = null;
    // A ":" at the start of a word begins the suggestion also where no emoji follows, as in "thanks :)". Ctrl+Enter,
    // which sends a comment, and Escape, which closes the view beside the list, wait while a dropbar is active, and
    // the menu's keys would keep ↑ and ↓ from the caret. So the menu is an active dropbar, and takes keys, only
    // while it shows emojis.
    let isMenuShown = false;

    const markMenuShownOrHidden = (props: SuggestionProps<EmojiItem>, forceOpen: boolean) => {
      isMenuShown = isEmojiMenuShown({ items: props.items, query: props.query, forceOpen });
      if (isMenuShown) props.editor.commands.addActiveDropbarExtension(CORE_EXTENSIONS.EMOJI);
      else props.editor.commands.removeActiveDropbarExtension(CORE_EXTENSIONS.EMOJI);
    };

    const handleClose = (editor?: Editor) => {
      component?.destroy();
      component = null;
      isMenuShown = false;
      (editor || editorRef)?.commands.removeActiveDropbarExtension(CORE_EXTENSIONS.EMOJI);
      const emojiStorage = (editor || editorRef)?.storage.emoji as ExtendedEmojiStorage;
      emojiStorage.forceOpen = false;
      cleanup();
    };

    return {
      onStart: (props) => {
        editorRef = props.editor;
        const emojiStorage = props.editor.storage.emoji as ExtendedEmojiStorage;
        const forceOpen = emojiStorage.forceOpen || false;
        component = new ReactRenderer<CommandListInstance, EmojisListDropdownProps>(EmojisListDropdown, {
          props: {
            ...props,
            onClose: () => handleClose(props.editor),
            forceOpen,
          } satisfies EmojisListDropdownProps,
          editor: props.editor,
          className: "fixed z-[100]",
        });
        if (!props.clientRect) return;
        markMenuShownOrHidden(props, forceOpen);
        const element = component.element as HTMLElement;
        cleanup = updateFloatingUIFloaterPosition(props.editor, element).cleanup;
      },

      onUpdate: (props) => {
        if (!component || !component.element) return;
        const emojiStorage = props.editor.storage.emoji as ExtendedEmojiStorage;
        const forceOpen = emojiStorage.forceOpen || false;
        component.updateProps({ ...props, forceOpen });
        if (!props.clientRect) return;
        markMenuShownOrHidden(props, forceOpen);
        cleanup();
        cleanup = updateFloatingUIFloaterPosition(props.editor, component.element as HTMLElement).cleanup;
      },
      onKeyDown: ({ event }) => {
        if (!isMenuShown) return false;

        if ([...DROPDOWN_NAVIGATION_KEYS, "Tab", "Escape"].includes(event.key)) {
          event.preventDefault();
          event.stopPropagation();
        }

        if (event.key === "Escape") {
          handleClose();
          return true;
        }

        return component?.ref?.onKeyDown({ event }) ?? false;
      },

      onExit: ({ editor }) => {
        component?.element.remove();
        handleClose(editor);
      },
    };
  },
};
