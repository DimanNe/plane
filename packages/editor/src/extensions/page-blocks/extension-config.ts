/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { mergeAttributes, Node } from "@tiptap/core";
// constants
import { ADDITIONAL_EXTENSIONS } from "@/constants/extensions";

export const NestedPageExtensionConfig = Node.create({
  name: ADDITIONAL_EXTENSIONS.NESTED_PAGE,
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      pageId: {
        default: undefined,
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: "nested-page",
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["nested-page", mergeAttributes(HTMLAttributes)];
  },
});

export const LinkPagesExtensionConfig = Node.create({
  name: ADDITIONAL_EXTENSIONS.LINK_PAGES,
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      source: {
        default: "parent_pages",
      },
      parent_id: {
        default: undefined,
      },
      creator_ids: {
        default: [],
        parseHTML: (element) => element.getAttribute("creator_ids")?.split(",").filter(Boolean) ?? [],
        renderHTML: (attributes) => ({ creator_ids: attributes.creator_ids.join(",") }),
      },
      depth: {
        default: "all",
        // "all", or a number of levels that stays a string
        parseHTML: (element) => element.getAttribute("depth"),
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: "link-pages",
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["link-pages", mergeAttributes(HTMLAttributes)];
  },
});
