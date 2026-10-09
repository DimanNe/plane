/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useRef } from "react";
import type { Dialog } from "@makeplane/propel/components/dialog";

type TDialogChangeEventDetails = Parameters<NonNullable<React.ComponentProps<typeof Dialog>["onOpenChange"]>>[1];

/**
 * Whether a press outside a dialog's popup landed on that dialog's own dimmed area.
 *
 * Menus and pickers that other code renders elsewhere on the page are outside the popup as well,
 * and choosing something in them must not count as dismissing the dialog. The dimmed area lives
 * in the same portal as the popup; those do not.
 */
export const isPressOnDialogBackdrop = (eventDetails: TDialogChangeEventDetails, popup: HTMLElement | null) => {
  const target = eventDetails.event.target;
  const portal = target instanceof Element ? target.closest("[data-base-ui-portal]") : null;
  return Boolean(popup && portal?.contains(popup));
};

// What a person can have changed in a dialog: the text it shows (a chosen option shows as the
// text of its control), what its fields hold, and its switches and checkboxes.
const describeContent = (popup: HTMLElement) =>
  [
    popup.textContent,
    ...Array.from(popup.querySelectorAll("input, textarea, select"), (field) =>
      field instanceof HTMLInputElement && (field.type === "checkbox" || field.type === "radio")
        ? String(field.checked)
        : (field as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value
    ),
    ...Array.from(popup.querySelectorAll("[aria-checked], [aria-pressed]"), (control) =>
      [control.getAttribute("aria-checked"), control.getAttribute("aria-pressed")].join()
    ),
  ].join("\n");

/**
 * Lets a form dialog close on a press outside it for as long as nothing in it was changed.
 *
 * A stray click must not throw away a half-filled form, which is why these dialogs ignored
 * outside presses altogether. A dialog that still looks as it did before the person first touched
 * it has nothing to lose, so there the press closes it like any other pop-up.
 *
 * Give `popupRef` to the `DialogContent`, and return early from `onOpenChange` when
 * `shouldIgnoreOutsidePress` says so.
 */
export const useUntouchedDialog = () => {
  const popup = useRef<HTMLElement | null>(null);
  // Taken at the first key or pointer press inside the dialog, when everything it loads has arrived.
  const untouchedContent = useRef<string | null>(null);

  const popupRef = useCallback((element: HTMLElement | null) => {
    if (!element) return undefined;
    popup.current = element;
    untouchedContent.current = null;
    const rememberUntouchedContent = () => {
      untouchedContent.current ??= describeContent(element);
    };
    const firstTouches = ["pointerdown", "keydown", "beforeinput"] as const;
    for (const type of firstTouches) element.addEventListener(type, rememberUntouchedContent, true);
    return () => {
      for (const type of firstTouches) element.removeEventListener(type, rememberUntouchedContent, true);
      popup.current = null;
    };
  }, []);

  const shouldIgnoreOutsidePress = useCallback((eventDetails: TDialogChangeEventDetails) => {
    if (eventDetails.reason !== "outside-press") return false;
    if (!popup.current || !isPressOnDialogBackdrop(eventDetails, popup.current)) return true;
    return untouchedContent.current !== null && untouchedContent.current !== describeContent(popup.current);
  }, []);

  return { popupRef, shouldIgnoreOutsidePress };
};
