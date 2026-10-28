/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observable, action, makeObservable } from "mobx";
// components
import type { IPowerKCommandRegistry } from "@/components/power-k/core/registry";
import { PowerKCommandRegistry } from "@/components/power-k/core/registry";
import type { TPowerKContextType, TPowerKPageType } from "@/components/power-k/core/types";

/**
 * The menu of a property of a work item that a key holds open, its states (S) or its priorities (P): of its selected
 * line of the list, or of the peek view. `focusedBefore`: what had the focus when the key was pressed, for the focus
 * to go back to when the menu closes.
 */
export type TPropertyMenuOfKey = {
  property: "state" | "priority";
  workItemId: string;
  place: "list" | "peek";
  focusedBefore: HTMLElement | undefined;
};

export interface IBasePowerKStore {
  // observables
  isPowerKModalOpen: boolean;
  isShortcutsListModalOpen: boolean;
  commandRegistry: IPowerKCommandRegistry;
  activeContext: TPowerKContextType | null;
  activePage: TPowerKPageType | null;
  topNavInputRef: React.RefObject<HTMLInputElement | null> | null;
  propertyMenuOfKey: TPropertyMenuOfKey | undefined;
  setActiveContext: (entity: TPowerKContextType | null) => void;
  setActivePage: (page: TPowerKPageType | null) => void;
  setTopNavInputRef: (ref: React.RefObject<HTMLInputElement | null> | null) => void;
  setPropertyMenuOfKey: (menu: TPropertyMenuOfKey | undefined) => void;
  // toggle actions
  togglePowerKModal: (value?: boolean) => void;
  toggleShortcutsListModal: (value?: boolean) => void;
}

export class BasePowerKStore implements IBasePowerKStore {
  // observables
  isPowerKModalOpen: boolean = false;
  isShortcutsListModalOpen: boolean = false;
  commandRegistry: IPowerKCommandRegistry = new PowerKCommandRegistry();
  activeContext: TPowerKContextType | null = null;
  activePage: TPowerKPageType | null = null;
  topNavInputRef: React.RefObject<HTMLInputElement | null> | null = null;
  propertyMenuOfKey: TPropertyMenuOfKey | undefined = undefined;

  constructor() {
    makeObservable(this, {
      // observable
      isPowerKModalOpen: observable.ref,
      isShortcutsListModalOpen: observable.ref,
      commandRegistry: observable.ref,
      activeContext: observable,
      activePage: observable,
      topNavInputRef: observable.ref,
      propertyMenuOfKey: observable.ref,
      // toggle actions
      togglePowerKModal: action,
      toggleShortcutsListModal: action,
      setActiveContext: action,
      setActivePage: action,
      setTopNavInputRef: action,
      setPropertyMenuOfKey: action,
    });
  }

  /**
   * Sets the active context entity
   * @param entity
   */
  setActiveContext = (entity: TPowerKContextType | null) => {
    this.activeContext = entity;
  };

  /**
   * Sets the active page
   * @param page
   */
  setActivePage = (page: TPowerKPageType | null) => {
    this.activePage = page;
  };

  /**
   * Sets the top nav input ref for keyboard shortcut access
   * @param ref
   */
  setTopNavInputRef = (ref: React.RefObject<HTMLInputElement | null> | null) => {
    this.topNavInputRef = ref;
  };

  /**
   * Sets the property menu that a key holds open
   * @param menu
   */
  setPropertyMenuOfKey = (menu: TPropertyMenuOfKey | undefined) => {
    this.propertyMenuOfKey = menu;
  };

  /**
   * Toggles the command palette modal
   * @param value
   * @returns
   */
  togglePowerKModal = (value?: boolean) => {
    if (value !== undefined) {
      this.isPowerKModalOpen = value;
    } else {
      this.isPowerKModalOpen = !this.isPowerKModalOpen;
    }
  };

  /**
   * Toggles the shortcut modal
   * @param value
   * @returns
   */
  toggleShortcutsListModal = (value?: boolean) => {
    if (value !== undefined) {
      this.isShortcutsListModalOpen = value;
    } else {
      this.isShortcutsListModalOpen = !this.isShortcutsListModalOpen;
    }
  };
}
