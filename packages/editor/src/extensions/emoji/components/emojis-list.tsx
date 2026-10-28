/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { FloatingOverlay } from "@floating-ui/react";
import type { SuggestionKeyDownProps, SuggestionProps } from "@tiptap/suggestion";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
// plane imports
import { useOutsideClickDetector } from "@plane/hooks";
import { cn } from "@plane/utils";

export type EmojiItem = {
  name: string;
  emoji: string;
  shortcodes: string[];
  tags: string[];
};

export type EmojiListRef = {
  onKeyDown: (props: SuggestionKeyDownProps) => boolean;
};

export type EmojisListDropdownProps = Pick<
  SuggestionProps<EmojiItem, { name: string }>,
  "items" | "command" | "query"
> & {
  onClose: () => void;
  forceOpen?: boolean;
};

// how many emojis the menu offers at most, in the editor and in a text field (emoji-menu-in-text-field.tsx)
export const EMOJI_MENU_LENGTH = 5;

/**
 * The menu shows once something is typed after ":", or at once when the slash command "Emoji" opened it, and only
 * while an emoji matches, so that typing on after no match is plain text, as with the slash command menu.
 */
export const isEmojiMenuShown = ({
  items,
  query,
  forceOpen,
}: Pick<EmojisListDropdownProps, "items" | "query" | "forceOpen">): boolean =>
  items.length > 0 && (query.length > 0 || !!forceOpen);

export const EmojisListDropdown = forwardRef(function EmojisListDropdown(
  props: EmojisListDropdownProps,
  ref: React.ForwardedRef<EmojiListRef>
) {
  const { items, command, query, onClose, forceOpen = false } = props;
  // states
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [isVisible, setIsVisible] = useState(false);
  // refs
  const dropdownContainerRef = useRef<HTMLDivElement>(null);

  const selectItem = useCallback(
    (index: number): void => {
      const item = items[index];
      if (item) {
        command({ name: item.name });
      }
    },
    [command, items]
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent): boolean => {
      if (event.key === "ArrowUp") {
        setSelectedIndex((prev) => (prev + items.length - 1) % items.length);
        return true;
      }

      if (event.key === "ArrowDown") {
        setSelectedIndex((prev) => (prev + 1) % items.length);
        return true;
      }

      if (event.key === "Enter" || event.key === "Tab") {
        selectItem(selectedIndex);
        return true;
      }

      return false;
    },
    [items.length, selectItem, selectedIndex]
  );

  // Show animation
  useEffect(() => {
    setIsVisible(false);
    const timeout = setTimeout(() => setIsVisible(true), 50);
    return () => clearTimeout(timeout);
  }, []);

  // Reset selection when items change
  useEffect(() => setSelectedIndex(0), [items]);

  // Scroll selected item into view
  useEffect(() => {
    const container = dropdownContainerRef.current;
    if (!container) return;

    const item = container.querySelector(`#emoji-item-${selectedIndex}`) as HTMLElement;
    if (item) {
      const containerRect = container.getBoundingClientRect();
      const itemRect = item.getBoundingClientRect();

      if (itemRect.top < containerRect.top || itemRect.bottom > containerRect.bottom) {
        item.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex]);

  useImperativeHandle(
    ref,
    () => ({
      onKeyDown: ({ event }: SuggestionKeyDownProps): boolean => handleKeyDown(event),
    }),
    [handleKeyDown]
  );

  useOutsideClickDetector(dropdownContainerRef, onClose);

  if (!isEmojiMenuShown({ items, query, forceOpen })) return null;

  return (
    <>
      {/* Backdrop */}
      <FloatingOverlay
        style={{
          zIndex: 99,
        }}
      />
      <div
        ref={dropdownContainerRef}
        className={cn(
          "invisible relative max-h-80 w-[14rem] space-y-2 overflow-y-auto rounded-md border-[0.5px] border-strong bg-surface-1 px-2 py-2.5 opacity-0 shadow-raised-200 transition-opacity",
          {
            "visible opacity-100": isVisible,
          }
        )}
        style={{
          zIndex: 100,
        }}
        onClick={(e) => {
          e.stopPropagation();
        }}
        onMouseDown={(e) => {
          e.stopPropagation();
        }}
      >
        {items.map((item, index) => {
          const isSelected = index === selectedIndex;
          const emojiKey = item.shortcodes.join(" - ");

          return (
            <button
              key={emojiKey}
              id={`emoji-item-${index}`}
              type="button"
              className={cn(
                "flex w-full items-center gap-2 truncate rounded-sm px-2 py-1.5 text-left text-13 text-secondary transition-colors duration-150 hover:bg-layer-1-hover",
                {
                  "bg-layer-1-hover": isSelected,
                }
              )}
              onClick={() => selectItem(index)}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              <span className="grid size-5 flex-shrink-0 place-items-center text-14">{item.emoji}</span>
              <span className="flex-grow truncate">
                <span className="font-medium">:{item.name}:</span>
              </span>
            </button>
          );
        })}
      </div>
    </>
  );
});

EmojisListDropdown.displayName = "EmojisListDropdown";
