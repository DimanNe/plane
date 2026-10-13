/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// components
import { STATE_SELECT_MENU } from "@/components/power-k/menu-picture";
// hooks
import { usePowerK } from "@/hooks/store/use-power-k";
// store
import type { IBasePowerKStore as IPowerKStore, TStateMenuOfKey } from "@/store/base-power-k.store";

type TStateMenuOfKeyProps = {
  open?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
  finalFocus?: boolean;
};

// One object for every menu that the key is not for: a component that is handed it is not drawn again for it.
const NOT_OF_KEY: TStateMenuOfKeyProps = {};

/**
 * Closes the state menu that the key S holds open. The focus, if the menu still has it, goes back to what had it
 * when S was pressed, and to nothing where that is no longer on the page: its line may have gone to another group.
 * It never goes to the control of the menu, where the component library would put it: from there no key is a
 * shortcut.
 */
export const closeStateMenuOfKey = (powerK: IPowerKStore) => {
  const menu = powerK.stateMenuOfKey;
  powerK.setStateMenuOfKey(undefined);
  const focused = document.activeElement;
  if (!menu || !(focused instanceof HTMLElement) || !focused.closest(STATE_SELECT_MENU.menu)) return;
  if (menu.focusedBefore?.isConnected) menu.focusedBefore.focus({ preventScroll: true });
  else focused.blur();
};

/**
 * What the state menu of a work item is given so that the key S can open it and the key after S can close it;
 * nothing for a menu that the key is not for, which then opens and closes by itself as always. A line of the list
 * names its work item only while it is the selected one: the other lines do not read the store, and are not drawn
 * again when the menu opens.
 */
export const useStateMenuOfKey = (
  place: TStateMenuOfKey["place"],
  workItemId: string | undefined
): TStateMenuOfKeyProps => {
  // store hooks
  const powerK = usePowerK();
  // derived values
  const menu = workItemId ? powerK.stateMenuOfKey : undefined;

  if (menu?.place !== place || menu.workItemId !== workItemId) return NOT_OF_KEY;
  return {
    open: true,
    onOpenChange: (isOpen: boolean) => {
      if (!isOpen) closeStateMenuOfKey(powerK);
    },
    // the focus is given back here, not by the menu
    finalFocus: false,
  };
};
