/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { useTranslation } from "@plane/i18n";
import { ContextMenu } from "./context-menu";
import { useMenuEditKey } from "./menu-edit-key";

type TItem = { label: string; isDisabled?: boolean };
type TMenuKind = "menu of a button" | "right-click menu";

/** A page with one menu of each kind the app has; `pressed` takes the label of every item that is activated. */
function Harness({ items, pressed }: { items: TItem[]; pressed: string[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();
  useMenuEditKey();
  return (
    <>
      {/* the word the rule looks for comes from the translations, which load after the first render */}
      <span data-testid="edit-word">{t("common.actions.edit")}</span>
      <Menu>
        <MenuTrigger render={<button type="button">More</button>} />
        <MenuContent>
          {items.map((item) => (
            <MenuItem
              key={item.label}
              label={item.label}
              disabled={item.isDisabled}
              onClick={() => pressed.push(item.label)}
            />
          ))}
        </MenuContent>
      </Menu>
      <div ref={parentRef} data-testid="line" />
      <ContextMenu
        parentRef={parentRef}
        items={items.map((item) => ({
          key: item.label,
          title: item.label,
          disabled: item.isDisabled,
          action: () => pressed.push(item.label),
        }))}
      />
    </>
  );
}

/** What a key leaves behind in an open menu with these items: E of a Latin layout unless another is given. */
async function pressKeyInMenu(kind: TMenuKind, items: TItem[], key?: { key: string; code: string }) {
  const user = userEvent.setup();
  const pressed: string[] = [];
  render(<Harness items={items} pressed={pressed} />);
  await waitFor(() => expect(screen.getByTestId("edit-word").textContent).toBe("Edit"));
  if (kind === "menu of a button") await user.click(screen.getByRole("button", { name: "More" }));
  else fireEvent.contextMenu(screen.getByTestId("line"));
  const menu = await screen.findByRole("menu");
  await waitFor(() => expect(menu.contains(document.activeElement)).toBe(true));
  if (key) fireEvent.keyDown(document.activeElement ?? menu, key);
  else await user.keyboard("e");
  // a menu that closes drops `data-open` before it leaves the page
  await waitFor(() => expect(pressed.length > 0).toBe(!screen.queryByRole("menu")?.hasAttribute("data-open")));
  const isMenuOpen = !!screen.queryByRole("menu")?.hasAttribute("data-open");
  const active = document.activeElement;
  // the item to which an open menu has moved its focus; a menu that closes gives the focus back in its own time
  const itemWithFocus = isMenuOpen && active?.getAttribute("role") === "menuitem" ? active.textContent : null;
  return { pressed, isMenuOpen, itemWithFocus };
}

describe("the key E in an open menu presses its item Edit", () => {
  const cases: {
    name: string;
    items: TItem[];
    key?: { key: string; code: string };
    expected: Awaited<ReturnType<typeof pressKeyInMenu>>;
  }[] = [
    {
      name: "Edit is pressed and the menu closes, though another item begins with the letter before it",
      items: [{ label: "Export" }, { label: "Edit" }, { label: "Delete" }],
      expected: { pressed: ["Edit"], isMenuOpen: false, itemWithFocus: null },
    },
    {
      name: "an item that names what is edited after the word is Edit too",
      items: [{ label: "Delete view" }, { label: "Edit view" }],
      expected: { pressed: ["Edit view"], isMenuOpen: false, itemWithFocus: null },
    },
    {
      name: "a disabled Edit: nothing is pressed, the menu stays open, and the focus goes to no other item",
      items: [{ label: "Export" }, { label: "Edit", isDisabled: true }],
      expected: { pressed: [], isMenuOpen: true, itemWithFocus: null },
    },
    {
      name: "a menu without Edit keeps the key: its focus goes to the item that begins with the letter",
      items: [{ label: "Delete" }, { label: "Export" }],
      expected: { pressed: [], isMenuOpen: true, itemWithFocus: "Export" },
    },
    {
      name: "a word that only begins like Edit is not Edit",
      items: [{ label: "Delete" }, { label: "Editor settings" }],
      expected: { pressed: [], isMenuOpen: true, itemWithFocus: "Editor settings" },
    },
    {
      name: "a layout without Latin letters: the key in the place of E is E",
      items: [{ label: "Export" }, { label: "Edit" }],
      key: { key: "у", code: "KeyE" },
      expected: { pressed: ["Edit"], isMenuOpen: false, itemWithFocus: null },
    },
    {
      name: "a Latin layout with another character in the place of E: that key is not E",
      items: [{ label: "Export" }, { label: "Edit" }],
      key: { key: ".", code: "KeyE" },
      expected: { pressed: [], isMenuOpen: true, itemWithFocus: null },
    },
  ];

  describe.each<TMenuKind>(["menu of a button", "right-click menu"])("in the %s", (kind) => {
    it.each(cases)("$name", async ({ items, key, expected }) => {
      expect(await pressKeyInMenu(kind, items, key)).toEqual(expected);
    });
  });
});
