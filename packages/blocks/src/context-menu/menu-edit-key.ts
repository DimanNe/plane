/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";

/** The key by its place on the keyboard where the layout has no Latin letters, as the shortcuts of the app. */
const isKeyE = (e: KeyboardEvent) => (e.key >= " " && e.key <= "~" ? e.key.toLowerCase() === "e" : e.code === "KeyE");

const isTextField = (element: HTMLElement) =>
  element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element.isContentEditable;

/** The label of a menu item: its first text. A description, where the item has one, comes after it. */
const getItemLabel = (item: Element) =>
  document.createTreeWalker(item, NodeFilter.SHOW_TEXT).nextNode()?.textContent?.trim().toLowerCase() ?? "";

/**
 * In an open menu that has an item Edit, the key E does what a click on that item does. Left to itself a menu
 * takes a letter as the beginning of a label, and moves its focus to the next item that begins with it.
 *
 * One rule for every menu of the app, the right-click menus and the menus of the "..." buttons alike. They are
 * built in many places from the menu items of the component library, which carry nothing that says what an
 * item is for, so the item is known by its label: the word Edit, alone or followed by what is edited.
 */
export const useMenuEditKey = () => {
  const { t } = useTranslation();
  const editWord = t("common.actions.edit").toLowerCase();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isKeyE(e) || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.repeat) return;
      if (!(e.target instanceof HTMLElement) || isTextField(e.target)) return;
      const items = e.target.closest('[role="menu"]')?.querySelectorAll<HTMLElement>('[role="menuitem"]');
      const editItem = Array.from(items ?? []).find((item) => {
        const label = getItemLabel(item);
        return label === editWord || label.startsWith(`${editWord} `);
      });
      if (!editItem) return;
      // The key is Edit's in this menu also while Edit is disabled: it must not move the focus to another item.
      e.preventDefault();
      e.stopPropagation();
      if (editItem.getAttribute("aria-disabled") !== "true") editItem.click();
    };
    // before the menu itself hears the key
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [editWord]);
};
