/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { computePosition, flip, shift, autoUpdate } from "@floating-ui/dom";
import type { Placement, ReferenceElement, Strategy } from "@floating-ui/dom";
import { posToDOMRect } from "@tiptap/core";
import type { Editor } from "@tiptap/core";

export type UpdateFloatingUIFloaterPosition = (
  editor: Editor,
  element: HTMLElement,
  options?: {
    elementStyle?: Partial<CSSStyleDeclaration>;
    placement?: Placement;
    strategy?: Strategy;
  }
) => {
  cleanup: () => void;
};

export const updateFloatingUIFloaterPosition: UpdateFloatingUIFloaterPosition = (editor, element, options) => {
  document.body.appendChild(element);
  // On <body>, the menu and the cover beside it, a press on which closes the menu, are outside of the panel that holds
  // the editor, such as the view of a work item beside the list, which closes on a press outside of it unless a menu
  // of its editor is open. The menu and the view handle the press on the document in the order their handlers were
  // added, and the view adds its handler anew each time it draws: when it drew while the menu showed, the menu has
  // closed by the time the view asks. The marker tells the view that the press was on a menu of its editor.
  // FOR_REVIEWER: other ways, not taken. (1) The view's hook (apps/web/hooks/use-peek-overview-outside-click.tsx) could
  // keep one handler for its whole life, so that it always runs before the menu's: it would still depend on an order
  // that nothing states. (2) The menus could leave the editor's list of open menus a task later, as the menus of a
  // table's rows and columns do (setTimeout 0): a timer, and a closed menu still counted as open until it fires. The
  // marker is read from the press itself (its composed path, fixed at dispatch), as for the emoji menu of a title
  // (emoji-menu-in-text-field.tsx), and covers the three menus placed here: emojis, slash commands and mentions. The
  // other readers of the marker (the extended sidebar, @plane/hooks' outside click detector, a nested submenu of
  // blocks' Select) now also ignore a press on the cover, which is what it is for.
  element.setAttribute("data-prevent-outside-click", "");

  const virtualElement: ReferenceElement = {
    getBoundingClientRect: () => posToDOMRect(editor.view, editor.state.selection.from, editor.state.selection.to),
  };

  const cleanup = autoUpdate(virtualElement, element, () => {
    computePosition(virtualElement, element, {
      placement: options?.placement ?? "bottom-start",
      strategy: options?.strategy ?? "fixed",
      middleware: [shift(), flip()],
    })
      .then(({ x, y, strategy }) => {
        Object.assign(element.style, {
          width: "max-content",
          position: strategy,
          left: `${x}px`,
          top: `${y}px`,
          ...options?.elementStyle,
        });
      })
      .catch((error) => console.error("An error occurred while updating floating UI floater position:", error));
  });

  return {
    cleanup,
  };
};
