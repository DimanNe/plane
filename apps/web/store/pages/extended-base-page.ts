/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { makeObservable, observable } from "mobx";
import type { TPage, TPageExtended } from "@plane/types";
import type { CoreRootStore } from "@/store/root.store";
import type { TBasePageServices } from "@/store/pages/base-page";

export type TExtendedPageInstance = TPageExtended & {
  asJSONExtended: TPageExtended;
};

export class ExtendedBasePage implements TExtendedPageInstance {
  parent_id: string | null | undefined;
  collection_id: string | null | undefined;
  sort_order: number | undefined;

  // oxlint-disable-next-line no-unused-vars
  constructor(store: CoreRootStore, page: TPage, services: TBasePageServices) {
    this.parent_id = page?.parent_id;
    this.collection_id = page?.collection_id;
    this.sort_order = page?.sort_order;

    makeObservable(this, {
      parent_id: observable.ref,
      collection_id: observable.ref,
      sort_order: observable.ref,
    });
  }

  get asJSONExtended(): TExtendedPageInstance["asJSONExtended"] {
    return {
      parent_id: this.parent_id,
      collection_id: this.collection_id,
      sort_order: this.sort_order,
    };
  }
}
